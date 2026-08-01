function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — AMP-PE (Approximate Message Passing with Parameter
% Estimation), Huang et al., MRM 2023. Nonlinear dipole inversion with a Laplace sparse-wavelet
% prior and a Gaussian-mixture noise model, solving over a linearized complex-exponential model.
%
% Reads  <inp>/localfield.nii.gz (ppm) + mask + params.json  (+ optional magnitude.nii.gz),
% writes <out>/chimap.nii.gz (ppm).
%
% This is the dipole-inversion stage only: the local (tissue) field is provided, so AMP-PE's own
% unwrapping / BET / PDF background removal / mask erosion are skipped. The local field (ppm) is
% turned into a simulated single-echo phase (radians) and fed to the AMP-PE nonlinear inversion,
% mirroring the "combined" path of the upstream qsm_multi_echo_combined.m.
%
% Bundled NIfTI toolbox + OS gunzip/gzip (no JVM); Wavelet Toolbox code is baked in by mcc. See BUILD.md.

    % When run uncompiled, put the vendored deps on the path. In the compiled binary they are
    % baked in by mcc (and the on-disk folders don't exist), so skip it.
    if ~isdeployed
        here = fileparts(mfilename('fullpath'));
        addpath(fullfile(here, 'nifti'));
        addpath(fullfile(here, 'functions'));
        addpath(genpath(fullfile(here, 'amp_pe_qsm')));
    end

    %% ---- inputs ----------------------------------------------------------------------------
    p    = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0   = p.B0_dir(:)';  b0 = b0 / norm(b0);
    vox  = p.voxel_size(:)';
    B0   = p.B0;

    lf_nii  = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    localfield = double(lf_nii.img);              % ppm
    mask = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;

    mat_sz = size(localfield);
    sx = mat_sz(1); sy = mat_sz(2); sz = mat_sz(3);

    % Optional magnitude: used both as the data-fidelity weight and (via a weighted magnitude image)
    % to build the wavelet morphology mask that injects anatomical edges into the prior. When absent
    % (a plain dipole run with no magnitude opted in) we fall back to uniform weights / no morphology
    % mask, so the method still runs.
    magPath = fullfile(inp, 'magnitude.nii.gz');
    have_mag = exist(magPath, 'file') == 2;
    if have_mag
        mag = double(read_niigz(magPath).img);
        if ndims(mag) == 4
            iMagWtd = sqrt(sum(mag.^2, 4));       % SNR-weighted magnitude across echoes
        else
            iMagWtd = abs(mag);
        end
    else
        iMagWtd = double(mask);
    end

    %% ---- parameters (overridable via /input/config.json or QSMCI_SET_* env) ----------------
    cfg = struct();
    cfgPath = fullfile(inp, 'config.json');
    if exist(cfgPath, 'file') == 2
        cfg = jsondecode(fileread(cfgPath));
    end
    wave_idx     = getparam(cfg, 'wave_idx', 1);          % Daubechies order: 1=db1 (best for straight B0), 2=db2
    nlevel       = getparam(cfg, 'nlevel', 3);            % wavelet decomposition levels
    wave_pec     = getparam(cfg, 'wave_pec', 0.85);       % morphology-mask retention fraction
    simulated_TE = getparam(cfg, 'simulated_TE', 8e-3);   % TE (s) used to simulate phase from the field
    max_lin_ite  = getparam(cfg, 'max_linearization_ite', 25);

    gyro_ratio = 42.58;                                   % MHz/T (matches upstream)

    %% ---- pad to a multiple of 2^nlevel for the wavelet transform ---------------------------
    % wavedec3/waverec3 at `nlevel` levels need each dimension divisible by 2^nlevel. The QSM
    % Challenge 2.0 phantom is 164x205x205 (none divisible by 8), which breaks the sparsifying
    % wavelet operators and yields a structureless map (xSIM ~ 0), while the 160^3 in-vivo grid
    % (all divisible by 8) reconstructs fine. Zero-pad the field / mask / magnitude to the next
    % multiple, reconstruct on that grid, then crop chi back at the end. The padded rim has mask = 0
    % so it never enters the data term; enlarging the FFT grid is standard (benign) for the kernel.
    orig_sz  = mat_sz;
    pad_mult = 2^nlevel;
    pad_sz   = ceil(orig_sz / pad_mult) * pad_mult;
    if ~isequal(pad_sz, orig_sz)
        localfield = local_pad(localfield, pad_sz);
        mask       = local_pad(mask,       pad_sz);
        iMagWtd    = local_pad(iMagWtd,     pad_sz);
        mat_sz = pad_sz;  sx = pad_sz(1);  sy = pad_sz(2);  sz = pad_sz(3);
    end

    %% ---- simulate single-echo tissue phase (radians) from the local field (ppm) ------------
    % mut_cst converts a ppm field to radians at simulated_TE. It appears in both the measurement and
    % the forward operator, so the recovered susceptibility is invariant to the simulated_TE choice
    % in the linear limit; simulated_TE only sets the operating point of the wrapped (exp) model.
    TE = simulated_TE;
    mut_cst = gyro_ratio * B0 * 2*pi * TE;

    phase_full = localfield * mut_cst;                    % radians, whole volume
    phase_image = phase_full(mask == 1);                  % Nvox x 1

    % Data-fidelity weights (per measurement). Normalise to unit mean within the mask for a stable,
    % reproducible scale independent of the magnitude's arbitrary units.
    if have_mag
        wv = iMagWtd(mask == 1);
        wv = wv / max(mean(wv), eps);
    else
        wv = ones(sum(mask(:)), 1);
    end
    weight_vect = wv;                                     % Nvox x 1 (single simulated echo)

    %% ---- operators -------------------------------------------------------------------------
    rotMat = [1 0 0; 0 1 0; b0];                          % GenerateDipoleFT3Drot uses only row 3 (B0 dir)
    dipoleFT = GenerateDipoleFT3Drot(mat_sz, vox, rotMat);
    A = SI_operator_withmask(dipoleFT, mat_sz, mask);

    % Wavelet transform (sparsifying basis). dwtmode('per') for periodic boundaries.
    dwtmode('per', 'nodisp');   % 2nd arg suppresses the status message (avoids a catalog lookup)
    wname = sprintf('db%d', wave_idx);
    X0 = zeros(sx, sy, sz);
    wav_vessel = wavedec3(X0, nlevel, wname);
    Psi  = @(x) [wavedec3(x, nlevel, wname)'];
    Psit = @(x) (waverec3(x));

    E_coef   = @(in) extract_3d_wav_coef(in);
    C_struct = @(in) construct_3d_wav_struct(in, wav_vessel);

    %% ---- parameter initialisation (L2/Tikhonov solve; used only to seed distributions) -----
    kernel  = dipole_kernel_angulated(mat_sz, vox, b0);
    phs_tissue = zeros(mat_sz);
    phs_tissue(mask == 1) = phase_image / mut_cst;        % back to ppm for the L2 seed
    chi_L2 = chiL2(phs_tissue, mask, kernel, 2e-2, mat_sz);
    X_init_par = real(chi_L2);  X_init_par(mask == 0) = 0;

    % Wavelet morphology mask: keep the largest wavelet coefficients of the (masked) magnitude image
    % so anatomical structure is preserved. Uniform (all-ones) when no magnitude is available.
    iMagWtd_m = iMagWtd;  iMagWtd_m(mask == 0) = 0;
    magwav = E_coef(Psi(iMagWtd_m));
    if have_mag
        magwav_abs = sort(abs(magwav), 'descend');
        cs = cumsum(magwav_abs) / sum(magwav_abs);
        thd = magwav_abs(max(1, length(cs(cs <= wave_pec))));
        wave_mask = double(abs(magwav) > thd);
    else
        wave_mask = ones(size(magwav));
    end

    %% ---- AMP-PE common GAMP parameters -----------------------------------------------------
    gamp_par.damp_rate       = getparam(cfg, 'damp_rate_sig', 0.01);
    gamp_par.max_pe_spar_ite = 5;
    gamp_par.max_pe_est_ite  = 5;
    gamp_par.cvg_thd         = 1e-6;
    gamp_par.kappa           = getparam(cfg, 'damp_rate_par', 0.1);
    gamp_par.sx = sx; gamp_par.sy = sy; gamp_par.sz = sz;
    gamp_par.mask = mask;
    gamp_par.wave_mask = wave_mask;

    X_init_par_psi = extract_3d_wav_coef(Psi(X_init_par));
    wav_coef_len = length(X_init_par_psi);
    M = sx*sy*sz;  N = wav_coef_len;
    A_wav = A_wav_single_3d_LinTrans(M, N, mat_sz, wav_coef_len, Psit, Psi, C_struct, E_coef);

    input_par  = struct();
    output_par = struct();

    %% ---- Step 1: preliminary reconstruction (single Gaussian noise) ------------------------
    X_init = zeros(size(X_init_par));
    for iter = 1:max_lin_ite
        if iter == 1
            output_par.tau_w_1 = 1e-12;
            gamp_par.x_hat_meas   = X_init;
            gamp_par.tau_x_meas   = var(X_init_par(:));
            gamp_par.s_hat_meas_1 = zeros(size(phase_image));
            gamp_par.x_hat_psi    = zeros(size(X_init_par_psi));
            gamp_par.p_hat_psi    = zeros(size(X_init_par));
            gamp_par.tau_x_hat_psi = var(X_init_par_psi(:));
            gamp_par.tau_p_psi     = A_wav.multSq(gamp_par.tau_x_hat_psi);
            input_par.lambda_x_hat_psi = 1/sqrt(var(abs(X_init_par_psi))/2);
        else
            output_par.tau_w_1 = output_par_new.tau_w_1;
            gamp_par.x_hat_meas   = res.x_hat_meas;
            gamp_par.tau_x_meas   = res.tau_x_meas;
            gamp_par.s_hat_meas_1 = res.s_hat_meas_1;
            gamp_par.x_hat_psi    = res.x_hat_psi;
            gamp_par.p_hat_psi    = res.p_hat_psi;
            gamp_par.tau_x_hat_psi = res.tau_x_hat_psi;
            gamp_par.tau_p_psi     = res.tau_p_psi;
            input_par.lambda_x_hat_psi = input_par_new.lambda_x_hat_psi;
        end

        A_X_init = real(A.times(X_init)) * mut_cst;
        der_1st  = 1i*exp(1i*A_X_init);
        A_qsm = A_qsm_weighted_nw_combine_real_LinTrans(numel(phase_image), sx*sy*sz, mat_sz, ...
                    der_1st.*weight_vect, A, mut_cst, size(phase_image,1), size(phase_image,2));
        y_upd = weight_vect .* (der_1st.*A_X_init + exp(1i*phase_image) - exp(1i*A_X_init));

        [res, input_par_new, output_par_new] = amp_pe_mri_qsm_awgn(A_qsm, A_wav, y_upd, gamp_par, input_par, output_par);
        X_init = res.x_hat_meas;
        fprintf('[step1 %d/%d]\n', iter, max_lin_ite);
    end

    %% ---- estimate outlier mixture from the step-1 residual ---------------------------------
    X_init = res.x_hat_meas;
    A_X_init = real(A.times(X_init)) * mut_cst;
    resid = weight_vect .* (exp(1i*A_X_init) - exp(1i*phase_image));
    resid_abs = abs(resid);
    resid_std = sqrt(mean(resid_abs.^2));
    gamma_est = length(resid(resid_abs > 3*resid_std)) / length(resid);
    psi_est   = var(resid(resid_abs > 3*resid_std));

    %% ---- Step 2: final reconstruction (2-component Gaussian mixture noise) -----------------
    for iter = 1:max_lin_ite
        if iter == 1
            output_par.theta_output = 0;
            output_par.phi_output   = output_par_new.tau_w_1;
            output_par.omega_output = 1;
            output_par.num_c_output = 1;
            output_par.gamma_output = gamma_est;
            output_par.psi_output   = psi_est;
        else
            output_par.theta_output = output_par_new.theta_output;
            output_par.phi_output   = output_par_new.phi_output;
            output_par.omega_output = output_par_new.omega_output;
            output_par.num_c_output = output_par_new.num_c_output;
            output_par.gamma_output = output_par_new.gamma_output;
            output_par.psi_output   = output_par_new.psi_output;
        end
        input_par.lambda_x_hat_psi = input_par_new.lambda_x_hat_psi;

        gamp_par.x_hat_meas   = res.x_hat_meas;
        gamp_par.tau_x_meas   = res.tau_x_meas;
        gamp_par.s_hat_meas_1 = res.s_hat_meas_1;
        gamp_par.x_hat_psi    = res.x_hat_psi;
        gamp_par.p_hat_psi    = res.p_hat_psi;
        gamp_par.tau_x_hat_psi = res.tau_x_hat_psi;
        gamp_par.tau_p_psi     = res.tau_p_psi;

        A_X_init = real(A.times(X_init)) * mut_cst;
        der_1st  = 1i*exp(1i*A_X_init);
        A_qsm = A_qsm_weighted_nw_combine_real_LinTrans(numel(phase_image), sx*sy*sz, mat_sz, ...
                    der_1st.*weight_vect, A, mut_cst, size(phase_image,1), size(phase_image,2));
        y_upd = weight_vect .* (der_1st.*A_X_init + exp(1i*phase_image) - exp(1i*A_X_init));

        [res, input_par_new, output_par_new] = amp_pe_mri_qsm_awgn_mix(A_qsm, A_wav, y_upd, gamp_par, input_par, output_par);
        X_init = res.x_hat_meas;
        fprintf('[step2 %d/%d]\n', iter, max_lin_ite);
    end

    chi = res.x_hat_meas;
    chi(mask == 0) = 0;
    chi = chi(1:orig_sz(1), 1:orig_sz(2), 1:orig_sz(3));   % crop back to the input grid

    %% ---- write output ----------------------------------------------------------------------
    lf_nii.img = single(chi);
    lf_nii.hdr.dime.datatype = 16;  lf_nii.hdr.dime.bitpix = 32;
    write_niigz(lf_nii, fullfile(out, 'chimap.nii.gz'));
end

function w = local_pad(v, sz)
% Zero-pad a 3D array up to sz at the high index of each dimension (no toolbox dependency).
    w = zeros(sz, 'like', v);
    w(1:size(v,1), 1:size(v,2), 1:size(v,3)) = v;
end

function v = getparam(cfg, name, default)
    if isstruct(cfg) && isfield(cfg, name) && ~isempty(cfg.(name))
        v = cfg.(name);
        if ischar(v) || isstring(v), v = str2double(v); end
    else
        v = default;
    end
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
