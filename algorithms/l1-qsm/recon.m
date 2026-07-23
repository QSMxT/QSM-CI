function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — L1-norm data-fidelity QSM (L1-QSM / PI-QSM).
% Milovic et al., MRM 2022; implementation from Carlos Milovic's FANSI toolbox (nlL1TV.m).
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
%
% Bundled: Jimmy Shen NIfTI toolbox + FANSI toolbox (installed at /opt/fansi in the image, added to
% path at compile time — see BUILD.md). OS gunzip/gzip (compiled binaries have no JVM).
% Optional <inp>/config.json overrides {alpha1, lambda, mu1, iterations, tol_update}.
%
% UNITS — CRITICAL. nlL1TV.m forms IS = exp(1i*params.input); its input MUST be in RADIANS.
% We convert ppm -> radians with phs_scale = 2*pi * 42.58 * B0 * TE, run the solver, then divide the
% output by the SAME phs_scale to return ppm (out.x is in radians). See nlL1TV.m header.
%
% LAMBDA — the L1 data-fidelity strength. Unlike FANSI, the fidelity weight must be rescaled by a
% lambda factor: weight = lambda * mask (mask in [0,1]). lambda < 1 rejects more inconsistent voxels.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';
    B0T = p.B0;                       % field strength (Tesla)
    TE  = p.TE(:)';  TE = TE(1);      % first echo time (s)

    % Defaults: FANSI-recommended alpha1; lambda=1 (no extra phase rejection); mu1 = 100*alpha1.
    cfg = struct('alpha1', 3e-4, 'lambda', 1.0, 'mu1', 3e-2, ...
                 'iterations', 50, 'tol_update', 1.0);
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

    % ppm -> radians (see UNITS note above)
    GYRO_MHz = 42.58;
    phs_scale = 2*pi * GYRO_MHz * B0T * TE;
    phase_rad = field * phs_scale;

    kernel = dipole_kernel_angulated(N, vox, b0);

    params = [];
    params.input        = single(phase_rad);
    params.K            = single(kernel);
    params.alpha1       = cfg.alpha1;
    params.mu1          = cfg.mu1;
    params.weight       = single(cfg.lambda * mask);  % lambda-scaled mask (no magnitude at dipole)
    params.maxOuterIter = cfg.iterations;
    params.tolUpdate    = cfg.tol_update;
    params.isGPU        = false;                       % MATLAB Runtime CPU-only at scoring time

    outs = nlL1TV(params);

    chi = double(outs.x) / phs_scale;                 % radians -> ppm
    chi = chi .* mask;

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
