function recon(inp, out)
% QSM-CI `field-mapping` stage in MATLAB: MEDI's field map, as the Cornell MEDI toolbox 2024.11.26's
% pipeline script makes it (README.m:80-95, unipolar readout):
%   iMag = sqrt(sum(abs(iField).^2,4));
%   [iFreq_raw, N_std] = Fit_ppm_complex(iField);     % complex fit, radians per echo spacing
%   iFreq = unwrapPhase(iMag, iFreq_raw, matrix_size); % region growing (mexUnwrap)
% Reads <inp>/phase.nii.gz (radians, echoes on the 4th axis) + magnitude + params.json, writes
% <out>/totalfield.nii.gz (ppm). The mask is not used: neither step takes one.
%
% iField is built as MEDI's Siemens and Philips readers build it, mag .* exp(-1i*phase)
% (Read_Siemens_DICOM.m:178, Read_DICOM.m:319); Fit_ppm_complex conjugates it, so a phase that
% grows with TE gives a positive iFreq. The field is converted to ppm with README.m's units:
% iFreq / (2*pi*delta_TE*CF) * 1e6, CF = 42.576 MHz/T * B0, delta_TE = TE(2) - TE(1).
% Fit_ppm_complex assumes evenly spaced echoes (README.m uses Fit_ppm_complex_TE otherwise), so
% recon.m stops on uneven spacing. One echo is fitted as Fit_ppm_complex does (zero phase at TE 0).
% README.m's next step, the R2* map for MEDI+0, is arlo(TE, abs(iField)); recon.m writes it as an
% intermediate, so ARLO is checked too (QSM-CI has no R2* stage).
%
% Bundled: Jimmy Shen NIfTI toolbox, the MEDI toolbox's Fit_ppm_complex.m, unwrapPhase.m, arlo.m
% and mexUnwrap compiled from its mexUnwrap.c (BUILD.md). OS gunzip/gzip (no JVM). Fit_ppm_complex's
% options can be overridden by <inp>/config.json {reltol, max_iter}.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, iMag,
% iFreq_raw, N_std, the unwrapped iFreq (radians over delta_TE), the totalfield, ARLO's R2* (Hz; 2+
% echoes) and intermediates.json (MATLAB version, thread count, where each function resolved).
% Unset, nothing changes.

    p  = jsondecode(fileread(fullfile(inp, 'params.json')));
    TE = double(p.TE(:)');

    cfg = struct('reltol', 1e-4, 'max_iter', 30);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nph = read_niigz(fullfile(inp, 'phase.nii.gz'));
    ph  = double(nph.img);
    mag = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    nte = size(ph, 4);
    if nte ~= numel(TE) || size(mag, 4) ~= nte
        error('recon:te', 'phase has %d echoes, magnitude %d, params.json %d echo times', ...
              nte, size(mag, 4), numel(TE));
    end
    if nte > 2 && max(abs(diff(diff(TE)))) > 1e-6 * max(TE)
        error('recon:te', 'Fit_ppm_complex needs evenly spaced echoes (TE = %s)', mat2str(TE));
    end
    matrix_size = [size(ph, 1) size(ph, 2) size(ph, 3)];

    iField = mag .* exp(-1i * ph);
    iMag = sqrt(sum(abs(iField).^2, 4));
    [iFreq_raw, N_std] = Fit_ppm_complex(iField, struct('reltol', double(cfg.reltol), ...
                                                        'max_iter', double(cfg.max_iter)));
    iFreq = unwrapPhase(iMag, iFreq_raw, matrix_size);

    [CF, delta_TE] = medi_units(p.B0, TE);
    total = iFreq / (2*pi * CF * delta_TE) * 1e6;                           % ppm

    tmpl = nph;
    tmpl.hdr.dime.dim(1) = 3;  tmpl.hdr.dime.dim(5) = 1;
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(tmpl, iMag, fullfile(idir, 'imag.nii.gz'));
        write_intermediate(tmpl, iFreq_raw, fullfile(idir, 'ifreq_raw.nii.gz'));
        write_intermediate(tmpl, N_std, fullfile(idir, 'n_std.nii.gz'));
        write_intermediate(tmpl, iFreq, fullfile(idir, 'ifreq.nii.gz'));
        write_intermediate(tmpl, total, fullfile(idir, 'totalfield_f64.nii.gz'));
        R2s = arlo(TE, abs(iField));
        if ~isempty(R2s), write_intermediate(tmpl, R2s, fullfile(idir, 'r2star.nii.gz')); end
        write_meta(idir, struct('reltol', cfg.reltol, 'max_iter', cfg.max_iter, 'CF', CF, ...
            'delta_TE', delta_TE));
    end

    tmpl.img = single(total);
    tmpl.hdr.dime.datatype = 16;  tmpl.hdr.dime.bitpix = 32;
    tmpl.hdr.dime.scl_slope = 1;  tmpl.hdr.dime.scl_inter = 0;
    write_niigz(tmpl, fullfile(out, 'totalfield.nii.gz'));
end

function [CF, delta_TE] = medi_units(B0, TE)
% README.m's CF (Hz) and delta_TE (s): 42.576 MHz/T times the field strength; the echo spacing.
    CF = 42.576e6 * double(B0);
    if numel(TE) > 1, delta_TE = TE(2) - TE(1); else, delta_TE = TE(1); end
end

function nii = read_niigz(f)
    t = [tempname '.nii'];
    system(sprintf('gunzip -c ''%s'' > ''%s''', f, t));
    nii = load_untouch_nii(t);
    delete(t);
    % load_untouch_nii returns the stored values: apply scl_slope/scl_inter where set.
    s = double(nii.hdr.dime.scl_slope); o = double(nii.hdr.dime.scl_inter);
    if s ~= 0 && ~(s == 1 && o == 0)
        nii.img = double(nii.img) * s + o;
        nii.hdr.dime.scl_slope = 1;  nii.hdr.dime.scl_inter = 0;
    end
end

function write_niigz(nii, f)
    t = [tempname '.nii'];
    save_untouch_nii(nii, t);
    system(sprintf('gzip -c ''%s'' > ''%s''', t, f));
    delete(t);
end

function tb = toolbox_functions()
    tb = {'Fit_ppm_complex', 'unwrapPhase', 'mexUnwrap', 'arlo'};
end

function idir = intermediates_dir(out)
% QSMCI_INTERMEDIATES: a directory, or 1 for <out>/intermediates. Unset or 0: none.
    idir = getenv('QSMCI_INTERMEDIATES');
    if strcmp(idir, '0'), idir = ''; end
    if strcmp(idir, '1'), idir = fullfile(out, 'intermediates'); end
    if isempty(idir), return; end
    if ~startsWith(idir, filesep), idir = fullfile(pwd, idir); end
    if ~exist(idir, 'dir'), mkdir(idir); end
end

function write_intermediate(tmpl, a, f)
% One intermediate as float64 NIfTI, through the input's untouched header (affine preserved).
    a = double(a);
    tmpl.img = a;
    tmpl.hdr.dime.datatype = 64;  tmpl.hdr.dime.bitpix = 64;
    tmpl.hdr.dime.dim(1) = max(3, ndims(a));
    tmpl.hdr.dime.dim(2:5) = [size(a, 1) size(a, 2) size(a, 3) size(a, 4)];
    tmpl.hdr.dime.scl_slope = 1;  tmpl.hdr.dime.scl_inter = 0;
    write_niigz(tmpl, f);
end

function write_meta(idir, m)
% intermediates.json: M plus the MATLAB version, the thread count, and where each function resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
