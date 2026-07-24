function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — FANSI nonlinear Total Variation dipole inversion.
% Fast Nonlinear Susceptibility Inversion (Milovic et al., MRM 2018, doi:10.1002/mrm.27073).
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
%
% Bundled: Jimmy Shen NIfTI toolbox (no Image Processing Toolbox) + FANSI toolbox (installed
% at /opt/fansi in the image, added to path at build/compile time — see BUILD.md). OS gunzip/gzip
% (compiled binaries have no JVM). Optional <inp>/config.json overrides {alpha1, mu1, iterations,
% tol_update, isTGV}.
%
% UNITS — CRITICAL. FANSI's nonlinear solvers (nlTV/nlTGV) contain a nonlinear data term
% sin(phi - phase); their input phase MUST be in RADIANS, not ppm. We convert the ppm local field
% to radians with the standard scale  phs_scale = 2*pi * gamma * B0 * TE  (gamma = 42.58 MHz/T,
% so gamma*1e6*1e-6 -> 42.58), run the solver, then divide the susceptibility output by the SAME
% phs_scale to return to ppm (FANSI's output x is in the same scaled units as its input). This
% mirrors script_qsmchallenge.m in the FANSI toolbox (phs_scale = TE*gyro*B0, chi = out.x/phs_scale).

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';
    B0T = p.B0;                       % field strength (Tesla)
    TE  = p.TE(:)';  TE = TE(1);      % first echo time (s); scale is linear so any TE cancels

    % Defaults (FANSI recommended: alpha1 ~ 1e-4..3e-4 gradient L1 penalty; mu1 = 100*alpha1).
    cfg = struct('alpha1', 3e-4, 'mu1', 3e-2, 'iterations', 150, ...
                 'tol_update', 0.1, 'isTGV', 0);
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

    % ppm -> radians (see UNITS note above). nlTV's nonlinear sin() data term diverges to NaN once
    % |phase| approaches pi: the fixed physical scale 2*pi*gamma*B0*TE overflows at 7 T on fields with
    % large outliers (the scoring phantom reaches ~0.8 ppm -> ~6 rad -> NaN by iter 3). Cap the scale
    % so the max in-brain phase stays ~1.5 rad. FANSI is scale-consistent (chi = x/phs_scale), so on
    % well-behaved fields the physical scale is used unchanged (e.g. the 3 T dev phantom, |field|<0.1
    % ppm) and the inversion is identical; the cap only tames the pathological high-field case.
    GYRO_MHz   = 42.58;                      % gyromagnetic ratio, MHz/T (absorbs the ppm 1e6 factor)
    phys_scale = 2*pi * GYRO_MHz * B0T * TE;
    fmax       = max(abs(field(mask)));      % largest in-brain |field| — drives the phase magnitude
    phs_scale  = min(phys_scale, 1.5 / max(fmax, eps));
    phase_rad  = field * phs_scale;

    % Dipole kernel (continuous, angulated for arbitrary B0 direction)
    kernel = dipole_kernel_angulated(N, vox, b0);

    params = [];
    params.input        = single(phase_rad);
    params.K            = single(kernel);
    params.alpha1       = cfg.alpha1;
    params.mu1          = cfg.mu1;
    params.weight       = single(mask);          % no magnitude at dipole stage -> mask weighting
    params.maxOuterIter = cfg.iterations;
    params.tolUpdate    = cfg.tol_update;
    params.isGPU        = false;                 % MATLAB Runtime CPU-only at scoring time

    if cfg.isTGV
        outs = nlTGV(params);
    else
        outs = nlTV(params);
    end

    chi = double(outs.x) / phs_scale;            % radians -> ppm
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
