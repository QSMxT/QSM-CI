function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB: Nonlinear Dipole Inversion (NDI; Polak et al., NMR Biomed 2020), the authors' ndi.m from the FANSI toolbox
% (gitlab.com/cmilovic/FANSI-toolbox, commit 93044a3, which QSM.rs's port cites).
% Reads <inp>/localfield (ppm) + magnitude (echoes on the 4th axis) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
%
% FANSI works on the local phase in radians, so the field is scaled by FANSI's phs_scale =
% te * gyro * B0, gyro = 2*pi*42.58 (script_invivo.m:58-62), and chi = out.x / phs_scale, as its
% scripts do. te is the first echo time (script_DICOM_Philips.m:364: "You may use also any individual echo time").
% The dipole kernel is dipole_kernel_angulated(N, voxel_size, B0_dir), as script_invivo.m:44 makes
% it (and nlTV/nlTGV build it when given none). The data weight is the magnitude as FANSI's in vivo example normalises it, min(2*Mask.*iMag/max(iMag(:)), 1) (script_invivo.m:52), with iMag the root sum of squares of the echo magnitudes (MEDI's iMag, which that example loads).
% Defaults: ndi.m's own: tau 2, alpha 1e-5, 100 iterations (ndi.m:31-49).
% isGPU is false: FANSI defaults to the GPU and falls back to the CPU when there is none; the
% compiled Runtime and the licensed runs both run on the CPU. chi is masked, as the other
% inversions leave it.
%
% Bundled: Jimmy Shen NIfTI toolbox, the FANSI toolbox's ndi.m and dipole_kernel_angulated.m
% (plain .m). OS gunzip/gzip (no JVM). Optional <inp>/config.json overrides the parameters in `cfg`
% below. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, the input
% phase (radians), the data weight, the unmasked solution out.x (radians) and intermediates.json
% (phs_scale, iterations, MATLAB version, thread count, where each function resolved). Unset,
% nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = double(p.voxel_size(:)');
    TE  = double(p.TE(:)');

    cfg = struct('tau', 2, 'alpha', 1e-5, 'max_iter', 100);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nlf   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(nlf.img);                                                % local field, ppm
    Mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));   % echoes on dim 4
    N = size(Mask);

    te = TE(1);
    gyro = 2*pi*42.58;
    phs_scale = te * gyro * double(p.B0);

    prm = struct();
    prm.input = field * phs_scale;                                          % radians
    prm.K = dipole_kernel_angulated(N, vox, b0);
    % FANSI's in vivo example (script_invivo.m:52): the magnitude normalised to [0, 1] and doubled.
    iMag = sqrt(sum(mag.^2, 4));
    prm.weight = min(2 * Mask .* iMag / max(iMag(:)), 1.0);
    prm.tau = double(cfg.tau);
    prm.alpha = double(cfg.alpha);
    prm.maxOuterIter = double(cfg.max_iter);
    prm.isGPU = false;
    res = ndi(prm);
    x = double(res.x);
    chi = x / phs_scale .* Mask;                                            % ppm

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nlf, prm.input, fullfile(idir, 'phase_input.nii.gz'));
        if isfield(prm, 'weight'), write_intermediate(nlf, prm.weight, fullfile(idir, 'weight.nii.gz')); end
        write_intermediate(nlf, x, fullfile(idir, 'x_rad.nii.gz'));
        meta = struct('te', te, 'phs_scale', phs_scale, 'cfg', cfg);
        if isfield(res, 'iter'), meta.iter = double(res.iter); end
        write_meta(idir, meta);
    end

    nlf.img = single(chi);
    nlf.hdr.dime.datatype = 16;  nlf.hdr.dime.bitpix = 32;
    nlf.hdr.dime.dim(1) = 3;  nlf.hdr.dime.dim(5) = 1;
    nlf.hdr.dime.scl_slope = 1;  nlf.hdr.dime.scl_inter = 0;
    write_niigz(nlf, fullfile(out, 'chimap.nii.gz'));
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
    tb = {'ndi', 'dipole_kernel_angulated'};
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
