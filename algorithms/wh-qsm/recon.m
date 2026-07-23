function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — Weak-Harmonic QSM (WH-QSM).
% Milovic et al., MRM 2019 (Weak-harmonic regularization, doi:10.1002/mrm.27483);
% implementation from Carlos Milovic's FANSI toolbox (WH_nlTV.m).
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
%
% STAGE = dipole (consumes the LOCAL field, not the total field). WH-QSM jointly estimates
% susceptibility AND a residual/remnant harmonic (background) field that survived background-field
% removal. Its own docstring: "used to remove background field remnants from *local* field maps and
% calculate the susceptibility of tissues simultaneously." So it corrects imperfect BFR at the
% dipole stage — it is NOT a full background-field-removal step and does NOT consume the total field.
%
% Bundled: Jimmy Shen NIfTI toolbox + FANSI toolbox (installed at /opt/fansi; added to path at
% compile time — see BUILD.md). OS gunzip/gzip (compiled binaries have no JVM).
% Optional <inp>/config.json overrides {alpha1, beta, mu1, iterations, tol_update}.
%
% UNITS — CRITICAL. WH_nlTV.m uses a nonlinear data term sin(z2 - phase); its input MUST be in
% RADIANS. We convert ppm -> radians with phs_scale = 2*pi * 42.58 * B0 * TE, run the solver, then
% divide the susceptibility output by the SAME phs_scale to return ppm (out.x is in radians).

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';
    B0T = p.B0;                       % field strength (Tesla)
    TE  = p.TE(:)';  TE = TE(1);      % first echo time (s)

    % Defaults: FANSI-recommended alpha1; beta=150 (harmonic-constraint weight, WH_nlTV default);
    % mu1 = 100*alpha1. Hundreds of iterations are recommended for the harmonic field to converge.
    cfg = struct('alpha1', 3e-4, 'beta', 150, 'mu1', 3e-2, ...
                 'iterations', 300, 'tol_update', 0.1);
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
    params.beta         = cfg.beta;
    params.mu1          = cfg.mu1;
    params.mask         = single(mask);          % ROI for susceptibility / harmonic estimation
    params.weight       = single(mask);          % no magnitude at dipole stage -> mask weighting
    params.maxOuterIter = cfg.iterations;
    params.tolUpdate    = cfg.tol_update;
    params.isGPU        = false;                  % MATLAB Runtime CPU-only at scoring time

    outs = WH_nlTV(params);

    chi = double(outs.x) / phs_scale;             % radians -> ppm
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
