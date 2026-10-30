function recon(inp, out)
% QSM-CI `bfr+dipole` span in MATLAB: preconditioned Total Field Inversion (TFI; Liu et al., MRM
% 2017), as the Cornell MEDI toolbox 2024.11.26 implements it: MEDI_L1.m with a preconditioner P in
% RDF.mat (parse_QSM_input.m), solving for y with chi = P*y over the whole field of view.
% Reads <inp>/totalfield.nii.gz (ppm) + magnitude (echoes on the 4th axis) + mask + params.json,
% writes <out>/chimap.nii.gz (ppm).
%
% Cornell's TFI script (TFI_L1.m) is not public, so what the toolbox does not settle comes from
% the paper, as QSM.rs's TFI port (src/inversion/tfi.rs) records:
%   - P = 1 in the mask and P_B = 30 outside (eq. 3; 30 is the paper's in-vivo value);
%   - the input is the total field over the whole field of view: no SMV ('nosmv'), since an SMV
%     high-pass would remove the background TFI fits;
%   - the data term is the linear one of eq. 5, MEDI_L1's 'linear' option (with the exponential
%     default, MEDI_L1 fails on in-vivo total fields: the field wraps inside exp(i*)).
% Everything else is MEDI_L1's own default: lambda 1000, MERIT on, 10 Gauss-Newton and 100 CG
% iterations, tolerances 0.1 and 0.01, percentage 0.9, data weighting on. No CSF zero reference.
% RDF.mat is filled as README.m does from QSM-CI's inputs: iMag the root sum of squares of the echo
% magnitudes, N_std from Fit_ppm_complex on them (its noise estimate depends only on the
% magnitudes), the field in radians over the echo spacing.
%
% Bundled: Jimmy Shen NIfTI toolbox, the MEDI toolbox's functions (plain .m). OS gunzip/gzip (no
% JVM). Optional <inp>/config.json overrides the parameters in `cfg` below. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, what
% MEDI_L1 reads from RDF.mat (rdf, n_std, imag, the preconditioner p) and intermediates.json
% (MEDI_L1's arguments, MATLAB version, thread count, where each function resolved). Unset,
% nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = double(p.voxel_size(:)');
    TE  = double(p.TE(:)');

    cfg = struct('lambda', 1000, 'precond', 30, 'linear', 1, 'merit', 1, 'percentage', 0.9, ...
                 'data_weighting', 1, 'cg_max_iter', 100, 'cg_tol', 0.01, 'max_iter', 10, ...
                 'tol_norm_ratio', 0.1);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    ntf   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(ntf.img);                                                % total field, ppm
    Mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));   % echoes on dim 4
    nte   = size(mag, 4);
    if nte ~= numel(TE)
        error('recon:te', 'magnitude has %d echoes but params.json lists %d echo times', nte, numel(TE));
    end
    matrix_size = size(Mask);
    voxel_size = vox; B0_dir = b0;

    [CF, delta_TE] = medi_units(p.B0, TE);
    iFreq = field * 1e-6 * 2*pi * CF * delta_TE;                            % radians over delta_TE
    RDF   = iFreq;                                                          % TFI inverts the total field
    iMag  = sqrt(sum(mag.^2, 4));
    [~, N_std] = Fit_ppm_complex(mag);
    P = Mask + double(cfg.precond) * (1 - Mask);                            % eq. 3

    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));
    save('RDF.mat', 'iFreq', 'RDF', 'N_std', 'iMag', 'Mask', 'P', ...
         'matrix_size', 'voxel_size', 'delta_TE', 'CF', 'B0_dir');
    args = {'lambda', cfg.lambda, 'nosmv', 'linear', logical(cfg.linear), ...
            'percentage', cfg.percentage, 'data_weighting', cfg.data_weighting, ...
            'cg_max_iter', cfg.cg_max_iter, 'cg_tol', cfg.cg_tol, 'max_iter', cfg.max_iter, ...
            'tol_norm_ratio', cfg.tol_norm_ratio};
    if cfg.merit, args = [args, {'merit'}]; else, args = [args, {'nomerit'}]; end
    chi = MEDI_L1(args{:});                                                 % P*y in ppm, masked by Mask
    cd(old);

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(ntf, RDF, fullfile(idir, 'rdf.nii.gz'));
        write_intermediate(ntf, N_std, fullfile(idir, 'n_std.nii.gz'));
        write_intermediate(ntf, iMag, fullfile(idir, 'imag.nii.gz'));
        write_intermediate(ntf, P, fullfile(idir, 'p.nii.gz'));
        write_meta(idir, struct('medi_args', {cellfun(@num2str, args, 'UniformOutput', false)}, ...
            'CF', CF, 'delta_TE', delta_TE));
    end

    ntf.img = single(chi);
    ntf.hdr.dime.datatype = 16;  ntf.hdr.dime.bitpix = 32;
    ntf.hdr.dime.dim(1) = 3;  ntf.hdr.dime.dim(5) = 1;
    ntf.hdr.dime.scl_slope = 1;  ntf.hdr.dime.scl_inter = 0;
    write_niigz(ntf, fullfile(out, 'chimap.nii.gz'));
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
    tb = {'MEDI_L1', 'parse_QSM_input', 'gradient_mask', 'dataterm_mask', 'cgsolve', 'reg_MEDI', 'dipole_kernel', 'Fit_ppm_complex'};
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
