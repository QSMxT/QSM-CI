function recon(inp, out)
% QSM-CI `chi-separation` stage — APART-QSM (Li et al., NeuroImage 2023; DOI 10.1016/j.neuroimage.2023.120148).
% Iterative susceptibility-source separation from complex multi-echo GRE. Reads canonical /input files,
% builds the inputs APART-QSM's single-orientation solver expects, calls it, and writes
% /output/chi-para.nii.gz (χ+, paramagnetic) and /output/chi-dia.nii.gz (χ−, diamagnetic as |χ−|).
%
% IMPORTANT — the core solver `apart_qsm_single_ori.m` is NOT distributed in the public AMRI-Lab/APART-QSM
% repo (only the demo, dipole_kernel, gradient_mask_all and @TVOP ship). This wrapper is written to the
% contract inferred from APART_QSM_single_ori_demo.m. It will error until that solver (obtained from the
% authors) is on the path via $APART_HOME. See BUILD.md / bunya_test.md.
%
% APART-QSM's contract (from the demo):
%   Res_map = apart_qsm_single_ori(mag_img, phi_local_img, r2_img, chi_img, params)
%     mag_img       : (x,y,z,echo) magnitude, arbitrary units
%     phi_local_img : (x,y,z,echo) LOCAL (background-removed) phase, radians
%     r2_img        : (x,y,z)      R2 map (s^-1) — monoexponential magnitude-decay rate (NOT R2*, NOT R2')
%     chi_img       : (x,y,z)      initial QSM (χ_total, ppm) — the demo seeds with STAR-QSM
%     params        : struct (mask,size,voxel_size,n_echo,TEs[s],gamma[MHz/T],B0[T],B0_dir,a,tol_a,
%                     lambda_r2prime,lambda_chi,lambda_TV)
%   Res_map(:,:,:,1) = X_para  (χ+, ppm, positive)
%   Res_map(:,:,:,2) = X_dia   (χ−, ppm, stored as a POSITIVE magnitude — "X_dia_abs" in the demo)
%   (:,:,:,3..7)     = phase_res, a_map, M0, R2star, R2prime  (unused here)

    addpath(genpath(getenv('APART_HOME')));     % APART-QSM repo (single_orientation + core solver)
    addpath(getenv('CHISEP_NIFTI'));            % Jimmy Shen NIfTI I/O (load_untouch_nii/save_untouch_nii)

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0  = p.B0;                                  % T
    TEs = p.TE(:)';                              % s (row vector)
    b0d = p.B0_dir(:)';                          % unit vector
    vox = p.voxel_size(:)';                      % mm
    gamma = 42.576;                              % MHz/T (¹H gyromagnetic ratio, as used by the demo)

    rd = @(f) double(getfield(read_niigz(fullfile(inp, f)), 'img'));
    mag4  = rd('magnitude.nii.gz');              % (x,y,z,echo)
    mn    = read_niigz(fullfile(inp, 'mask.nii.gz'));
    mask  = double(mn.img) > 0.5;
    n_echo = size(mag4, 4);
    msize  = size(mag4(:,:,:,1));

    % ---- LOCAL phase per echo -------------------------------------------------------------------
    % APART wants per-echo local (background-removed) phase in radians. Our pipeline provides a single
    % 3D local field in ppm (localfield.nii.gz), so we re-project it to per-echo phase:
    %   phi_e(x) = localfield_ppm(x) * 1e-6 * (gamma[MHz/T] * 1e6) * B0[T] * 2*pi * TE_e[s]
    localfield_ppm = rd('localfield.nii.gz');    % ppm
    phi_local_img = zeros([msize n_echo]);
    for e = 1:n_echo
        phi_local_img(:,:,:,e) = localfield_ppm * 1e-6 * (gamma*1e6) * B0 * 2*pi * TEs(e);
    end

    % ---- R2 map ---------------------------------------------------------------------------------
    % APART wants an R2 map. Our pipeline does not carry R2; the closest available quantity is R2*
    % estimated from the multi-echo magnitude by a log-linear (weighted) fit. This is an APPROXIMATION
    % (R2* = R2 + R2'); see BUILD.md "Risks". If a true R2 map is added to /input later, prefer it.
    r2_img = estimate_r2star(mag4, TEs, mask);

    % ---- initial QSM (χ_total) ------------------------------------------------------------------
    chi_img = rd('chimap.nii.gz');               % ppm; demo seeds with STAR-QSM

    % ---- params ---------------------------------------------------------------------------------
    params = struct();
    params.mask       = mask;
    params.size       = msize;
    params.voxel_size = vox;
    params.n_echo     = n_echo;
    params.TEs        = TEs;
    params.gamma      = gamma;                   % MHz/T
    params.B0         = B0;                       % T
    params.B0_dir     = b0d;
    params.a          = 323.5;                    % magnitude-decay kernel, Hz/ppm (demo default)
    params.tol_a      = 0.3;
    params.lambda_r2prime = 0.1;
    params.lambda_chi     = 10;
    params.lambda_TV      = 1;

    Res_map = apart_qsm_single_ori(mag4, phi_local_img, r2_img, chi_img, params);

    x_para = Res_map(:,:,:,1);                    % χ+ (ppm, positive)
    x_dia  = Res_map(:,:,:,2);                    % χ− already stored as positive magnitude (X_dia_abs)

    % Our χ− convention is also a POSITIVE magnitude, so no sign flip needed. abs() is a guard only.
    write_niigz(setimg(mn, single(x_para .* mask)),       fullfile(out, 'chi-para.nii.gz'));
    write_niigz(setimg(mn, single(abs(x_dia) .* mask)),   fullfile(out, 'chi-dia.nii.gz'));
end

function r2 = estimate_r2star(mag4, TEs, mask)
% Weighted log-linear R2* fit across echoes (fallback for the R2 map APART expects).
    sz = size(mag4); n = sz(4);
    S  = max(reshape(mag4, [], n), eps);         % (Nvox, echo)
    y  = log(S);                                 % ln signal
    w  = S.^2;                                   % magnitude-weighted (SNR ~ magnitude)
    t  = TEs(:);                                 % (echo,1)
    Sw  = sum(w, 2);
    St  = sum(w .* t', 2);
    Stt = sum(w .* (t'.^2), 2);
    Sy  = sum(w .* y, 2);
    Sty = sum(w .* (t' .* y), 2);
    denom = (Sw .* Stt - St.^2);
    slope = (Sw .* Sty - St .* Sy) ./ max(denom, eps);   % d(ln S)/dTE = -R2*
    r2 = reshape(max(-slope, 0), sz(1:3)) .* mask;       % s^-1, clamped >= 0
end

function nii = setimg(tmpl, img)
    nii = tmpl; nii.img = img;
    nii.hdr.dime.datatype = 16; nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3; nii.hdr.dime.dim(5) = 1;
end
function nii = read_niigz(f)
    t = [tempname '.nii']; system(sprintf('gunzip -c ''%s'' > ''%s''', f, t)); nii = load_untouch_nii(t); delete(t);
end
function write_niigz(nii, f)
    t = [tempname '.nii']; save_untouch_nii(nii, t); system(sprintf('gzip -c ''%s'' > ''%s''', t, f)); delete(t);
end
