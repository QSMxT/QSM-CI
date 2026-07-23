function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — Hybrid Data-fidelity QSM (HD-QSM).
% Lambert et al., MRM 2022 (doi:10.1002/mrm.29218). Two-stage inversion: an L1 data-fidelity stage
% estimates a discrepancy map, then an L2 stage re-weighted by it. Repo: github.com/mglambert/HD-QSM.
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
%
% Bundled: Jimmy Shen NIfTI toolbox + HD-QSM (HDQSM.m) + FANSI toolbox (HDQSM depends on FANSI's
% `gradient_calc` and a dipole-kernel function). Installed at /opt/hdqsm and /opt/fansi; added to
% path at compile time — see BUILD.md. OS gunzip/gzip (compiled binaries have no JVM).
% Optional <inp>/config.json overrides {alphaL2, mu1L2, tol_update, iterationsL1, iterationsL2}.
%
% UNITS. HD-QSM is a LINEAR inversion (real(ifftn(kernel.*Fx)); no sin/exp), so it is scale-linear:
% output susceptibility is in the same units as the input field. We therefore feed the ppm local
% field DIRECTLY and get a ppm chimap out — no radian conversion needed (unlike the FANSI nonlinear
% methods). The regularization weight `alphaL2` is calibrated to this ppm (B0-normalized) field
% scale, matching the toolbox's own example (params.input = phase_use/phase_scale, which yields the
% ppm-normalized field).

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';

    % Defaults from the HDQSM.m example (alphaL2 = 10^-4.785; mu1L2 = 10*alphaL2). L1-stage params
    % (alphaL1, mu1L1) default inside HDQSM to sqrt(alphaL2), sqrt(mu1L2). Iterations: L1=20, L2=80.
    cfg = struct('alphaL2', 10^(-4.785), 'mu1L2', 10*10^(-4.785), ...
                 'tol_update', 1.0, 'iterationsL1', 20, 'iterationsL2', 80);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    % --- inputs ---
    nlf   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(nlf.img);                                     % local field, ppm
    mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;

    N = size(field);

    % Dipole kernel (continuous, angulated for arbitrary B0 direction; from FANSI)
    kernel = dipole_kernel_angulated(N, vox, b0);

    params = [];
    params.input          = single(mask .* field);   % ppm local field (linear method -> ppm out)
    params.kernel         = single(kernel);
    params.mask           = single(mask);
    params.weight         = single(mask);             % no magnitude at dipole stage -> mask weighting
    params.alphaL2        = cfg.alphaL2;
    params.mu1L2          = cfg.mu1L2;
    params.tol_update     = cfg.tol_update;
    params.maxOuterIterL1 = cfg.iterationsL1;
    params.maxOuterIterL2 = cfg.iterationsL2;

    outs = HDQSM(params);

    chi = double(outs.x) .* mask;                     % already ppm (linear method)

    nlf.img = single(chi);
    nlf.hdr.dime.datatype = 16;  nlf.hdr.dime.bitpix = 32;
    nlf.hdr.dime.dim(1) = 3;  nlf.hdr.dime.dim(5) = 1;
    write_niigz(nlf, fullfile(out, 'chimap.nii.gz'));
end

function nii = read_niigz(f)
    t = [tempname '.nii'];
    system(sprintf('gunzip -c ''%s'' > ''%s''', f, t));
    nii = load_untouch_nii(t);
    delete(t);
end

function write_niigz(nii, f)
    t = [tempname '.nii'];
    save_untouch_nii(nii, t);
    system(sprintf('gzip -c ''%s'' > ''%s''', t, f));
    delete(t);
end
