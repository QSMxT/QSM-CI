function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB: Projection onto Dipole Fields, the authors' PDF.m (Cornell MEDI
% toolbox 2024.11.26, the release QSM.rs's PDF port follows).
% Reads <inp>/totalfield.nii.gz (ppm) + magnitude (echoes on the 4th axis) + mask + params.json,
% writes <out>/localfield.nii.gz (ppm).
%
% What MEDI's pipeline script (README.m:80-124) does, from QSM-CI's inputs:
%   [iFreq_raw, N_std] = Fit_ppm_complex(iField);  iFreq = unwrapPhase(...);
%   RDF = PDF(iFreq, N_std, Mask, matrix_size, voxel_size, B0_dir);
% The total field is the unwrapped iFreq, converted from ppm to radians over the echo spacing as
% MEDI holds it. N_std is Fit_ppm_complex's noise estimate (dp1), which depends only on the echo
% magnitudes, so Fit_ppm_complex on the magnitudes gives exactly the N_std the complex echoes
% would (as medi-cornell). PDF's weighting and CG tolerance depend on N_std relative to the field,
% so both are in MEDI's units. PDF.m's own defaults: tol 0.1, n_CG 30, 'imagespace', n_pad 40.
%
% Bundled: Jimmy Shen NIfTI toolbox, the MEDI toolbox's functions (no pcode, no mex on this path).
% OS gunzip/gzip (no JVM). Optional <inp>/config.json overrides {tol, n_cg, space, n_pad}. See
% BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, the total
% field in MEDI's units (ifreq), N_std, PDF's output in MEDI's units (rdf), and intermediates.json
% (PDF's arguments, MATLAB version, thread count, where each function resolved). Unset, nothing
% changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = double(p.voxel_size(:)');
    TE  = double(p.TE(:)');

    cfg = struct('tol', 0.1, 'n_cg', 30, 'space', 'imagespace', 'n_pad', 40);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nii   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(nii.img);                                                % total field, ppm
    Mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));   % echoes on dim 4
    nte   = size(mag, 4);
    if nte ~= numel(TE)
        error('recon:te', 'magnitude has %d echoes but params.json lists %d echo times', nte, numel(TE));
    end
    matrix_size = size(Mask);

    % MEDI's units (README.m, Read_DICOM): CF the centre frequency, delta_TE the echo spacing
    % TE(2) - TE(1), or TE for one echo. The field is radians accumulated over delta_TE.
    [CF, delta_TE] = medi_units(p.B0, TE);
    iFreq = field * 1e-6 * 2*pi * CF * delta_TE;
    [~, N_std] = Fit_ppm_complex(mag);

    RDF = PDF(iFreq, N_std, Mask, matrix_size, vox, b0, ...
              double(cfg.tol), double(cfg.n_cg), char(cfg.space), double(cfg.n_pad));
    local = RDF / (2*pi * CF * delta_TE) * 1e6;                             % ppm

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nii, iFreq, fullfile(idir, 'ifreq.nii.gz'));
        write_intermediate(nii, N_std, fullfile(idir, 'n_std.nii.gz'));
        write_intermediate(nii, RDF, fullfile(idir, 'rdf.nii.gz'));
        write_meta(idir, struct('tol', cfg.tol, 'n_cg', cfg.n_cg, 'space', cfg.space, ...
            'n_pad', cfg.n_pad, 'CF', CF, 'delta_TE', delta_TE, 'isreal', isreal(RDF)));
    end

    nii.img = single(local);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3;  nii.hdr.dime.dim(5) = 1;
    nii.hdr.dime.scl_slope = 1;  nii.hdr.dime.scl_inter = 0;
    write_niigz(nii, fullfile(out, 'localfield.nii.gz'));
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
    tb = {'PDF', 'Fit_ppm_complex', 'dipole_kernel', 'dipole_term', 'cgsolve', 'padarray'};
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
