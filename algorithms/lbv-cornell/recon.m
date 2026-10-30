function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB: Laplacian Boundary Value background removal, the authors' LBV.m
% and its full-multigrid solver mexMGv6 (Dong Zhou; Cornell MEDI toolbox 2024.11.26).
% Reads <inp>/totalfield.nii.gz (ppm) + mask + params.json, writes <out>/localfield.nii.gz (ppm).
%
% MEDI's pipeline script (README.m:129, the commented alternative to PDF) runs
% LBV(iFreq, Mask, matrix_size, voxel_size, 0.005) on the unwrapped field. recon.m runs LBV.m with
% its own defaults (tol 0.01, depth -1 = automatic, peel 0, N1/N2/N3 30/100/100); config.json can set
% tol 0.005 for the README's call. The field is converted from ppm to MEDI's units (radians over the
% echo spacing) first, because mexMGv6 stops on an absolute update tolerance (MG::relax: the
% coarsest-grid iteration runs while the change exceeds tol), so the result depends on the scale.
% mexMGv6 computes in single precision. LBV's output is the local field on its interior (the mask
% minus its boundary layer and `peel` more layers), and 0 elsewhere.
%
% Bundled: Jimmy Shen NIfTI toolbox, MEDI's LBV.m and mexMGv6 compiled from the toolbox's
% mexMGv6.cpp (its shipped mexMGv6.mexa64 predates the source and returns no interior; BUILD.md). OS gunzip/gzip (no JVM). Optional <inp>/config.json overrides {tol, depth, peel, n1, n2,
% n3}.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, the total
% field in MEDI's units (ifreq), LBV's output in those units (fl), its interior mask, and
% intermediates.json (LBV's arguments, MATLAB version, thread count, where each function
% resolved). Unset, nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    vox = double(p.voxel_size(:)');
    TE  = double(p.TE(:)');

    cfg = struct('tol', 0.01, 'depth', -1, 'peel', 0, 'n1', 30, 'n2', 100, 'n3', 100);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nii   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(nii.img);                                                % total field, ppm
    Mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);
    matrix_size = size(Mask);

    [CF, delta_TE] = medi_units(p.B0, TE);
    iFreq = field * 1e-6 * 2*pi * CF * delta_TE;                            % radians over delta_TE
    [fL, interior] = LBV(iFreq, Mask, matrix_size, vox, double(cfg.tol), double(cfg.depth), ...
                         double(cfg.peel), double(cfg.n1), double(cfg.n2), double(cfg.n3));
    local = fL / (2*pi * CF * delta_TE) * 1e6;                              % ppm

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nii, iFreq, fullfile(idir, 'ifreq.nii.gz'));
        write_intermediate(nii, fL, fullfile(idir, 'fl.nii.gz'));
        write_intermediate(nii, interior, fullfile(idir, 'lbv_interior.nii.gz'));
        write_meta(idir, struct('tol', cfg.tol, 'depth', cfg.depth, 'peel', cfg.peel, 'n1', cfg.n1, ...
            'n2', cfg.n2, 'n3', cfg.n3, 'CF', CF, 'delta_TE', delta_TE));
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
    tb = {'LBV', 'mexMGv6'};
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
