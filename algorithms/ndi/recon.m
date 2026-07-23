function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — Nonlinear Dipole Inversion (NDI).
% Polak/Bilgic et al., NMR Biomed 2020; implementation from Carlos Milovic's FANSI toolbox (ndi.m).
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
%
% Bundled: Jimmy Shen NIfTI toolbox + FANSI toolbox (installed at /opt/fansi in the image, added to
% path at compile time — see BUILD.md). OS gunzip/gzip (compiled binaries have no JVM).
% NDI is essentially parameter-tuning-free; optional <inp>/config.json overrides {tau, iterations,
% alpha} are exposed for experimentation.
%
% UNITS — CRITICAL. ndi.m uses a nonlinear data term sin(phix - phase); its input field MUST be in
% RADIANS. We convert ppm -> radians with phs_scale = 2*pi * 42.58 * B0 * TE (42.58 MHz/T absorbs
% the ppm 1e6 factor), run the solver, then divide the output by the SAME phs_scale to return ppm
% (out.x is in radians, i.e. the same scaled units as the input). See ndi.m header.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';
    B0T = p.B0;                       % field strength (Tesla)
    TE  = p.TE(:)';  TE = TE(1);      % first echo time (s)

    % NDI is tuning-free; these are the FANSI ndi.m defaults, exposed for override.
    cfg = struct('tau', 2.0, 'iterations', 100, 'alpha', 1e-5);
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
    params.weight       = single(mask);          % no magnitude at dipole stage -> mask weighting
    params.tau          = cfg.tau;
    params.alpha        = cfg.alpha;
    params.maxOuterIter = cfg.iterations;
    params.isGPU        = false;                  % MATLAB Runtime CPU-only at scoring time

    outs = ndi(params);

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
