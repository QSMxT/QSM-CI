function recon(inp, out)
% QSM-CI `chi-separation` stage — APART-QSM (Li/Wang et al., NeuroImage 274:120148, 2023;
% github.com/AMRI-Lab/APART-QSM), a GRE-based (signal-domain) iterative sub-voxel susceptibility
% source-separation method.
%
% APART-QSM alternately solves a voxel-wise magnitude-decay kernel (the "a-map") and the sub-voxel
% χ+/χ− split via an iterative data-fitting scheme (per-echo complex GRE signal fit + TV-regularised
% dipole inversion). Its core solver is `apart_qsm_single_ori`. See the demo
% APART_QSM_single_ori_demo.m for the reference call convention:
%
%   Res_map = apart_qsm_single_ori(mag_img, phi_local_img, r2_img, chi_img, params)
%     mag_img       [X Y Z nEcho]  multi-echo magnitude
%     phi_local_img [X Y Z nEcho]  per-echo LOCAL (tissue) phase, radians
%     r2_img        [X Y Z]        R2 map (Hz)
%     chi_img       [X Y Z]        initial QSM / χ_total (ppm) (reference uses STAR-QSM)
%     params        struct         mask,size,voxel_size,n_echo,TEs,gamma,B0,B0_dir,a,tol_a,lambdas
%   Res_map(:,:,:,1)=X_para (χ+, ppm), (:,:,:,2)=X_dia_abs (|χ−|, ppm, POSITIVE magnitude).
%
% ============================ IMPORTANT — MISSING CORE SOLVER ============================
% The public APART-QSM repo (AMR-Lab, commit c49bad4) ships ONLY the demos + helpers
% (dipole_kernel, gradient_mask_all, @TVOP) and .mat test data. The actual solver
% `apart_qsm_single_ori` / `apart_qsm_multi_ori` IS NOT DISTRIBUTED. This wrapper is written to the
% published call convention but CANNOT run until that solver is obtained from the authors and placed
% on the path ($APART_CORE or apart_core/). See BUILD.md §0. Do NOT compile/score until then.
% ========================================================================================
%
% ADAPTATION for QSM-CI: the chi-separation stage provides a single 3D local field (localfield.nii.gz,
% ppm) rather than per-echo local phase. Since χ (and hence the local field) is echo-independent, we
% synthesise the per-echo local phase the demo expects from that field:
%     phi_local(:,:,:,e) = localfield_ppm * 1e-6 * gamma_rad * B0 * TE(e)
% We feed the provided χ_total (chimap.nii.gz) as the initial QSM, and the provided R2′ (r2prime.nii.gz,
% Hz) as the R2 term. Writes chi-para.nii.gz (χ+, ppm) and chi-dia.nii.gz (χ−, POSITIVE magnitude, ppm).

    % When run uncompiled, put the vendored deps on the path. In the compiled binary they are baked in
    % by mcc (and the on-disk folders don't exist), so skip. $APART_CORE points at the (author-obtained)
    % core solver directory; apart_utils/ holds the repo's published helpers; nifti/ is the NIfTI I/O.
    if ~isdeployed
        here = fileparts(mfilename('fullpath'));
        addpath(fullfile(here, 'nifti'));
        addpath(fullfile(here, 'apart_utils'));
    end
    addpath_env('APART_CORE', true);   % the author-obtained apart_qsm_single_ori solver (see BUILD.md §0)
    addpath_env('APART_UTILS', true);  % override for the vendored helpers, if set
    addpath_env('CHISEP_NIFTI', false);

    %% ---- inputs ---------------------------------------------------------------------------------
    p     = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0    = p.B0;                       % T
    TE    = p.TE(:)';                   % echo times (s)
    b0d   = p.B0_dir(:)';
    vox   = p.voxel_size(:)';
    gamma = 42.576;                     % gyromagnetic ratio (MHz/T), as in the APART demo
    gamma_rad = gamma * 1e6 * 2*pi;     % rad/(s·T) for ppm->radians phase conversion

    rd = @(f) double(getfield(read_niigz(fullfile(inp, f)), 'img'));
    mag_multi_echo = rd('magnitude.nii.gz');        % [X Y Z nEcho]
    localfield     = rd('localfield.nii.gz');       % ppm (single 3D tissue field)
    r2prime        = rd('r2prime.nii.gz');          % Hz
    chimap         = rd('chimap.nii.gz');           % χ_total (ppm) — initial QSM
    mn   = read_niigz(fullfile(inp, 'mask.nii.gz'));
    mask = double(mn.img) > 0.5;

    [N1, N2, N3, nTE] = size(mag_multi_echo);
    if numel(TE) ~= nTE
        error('APART: params TE has %d entries but magnitude has %d echoes', numel(TE), nTE);
    end

    % Synthesise per-echo local phase (radians) from the provided single 3D local field (ppm). χ is
    % echo-independent, so the local field scales linearly with TE (see header note).
    phi_local = zeros(N1, N2, N3, nTE);
    for e = 1:nTE
        phi_local(:,:,:,e) = (localfield * 1e-6 * gamma_rad * B0 * TE(e)) .* mask;
    end
    mag_multi_echo = mag_multi_echo .* mask;

    %% ---- parameters (overridable via /input/config.json) ---------------------------------------
    cfg = struct();
    cfgPath = fullfile(inp, 'config.json');
    if exist(cfgPath, 'file') == 2; cfg = jsondecode(fileread(cfgPath)); end
    gv = @(name, def) getcfg(cfg, name, def);

    params = struct();
    params.mask          = mask;
    params.size          = [N1 N2 N3];
    params.voxel_size    = vox;
    params.n_echo        = nTE;
    params.TEs           = TE(:);
    params.gamma         = gamma;
    params.B0            = B0;
    params.B0_dir        = b0d;
    % magnitude decay kernel (Hz/ppm). The demo uses 323.5 at 3T; our chisep phantom's R2′ model uses
    % a single Dr=137 Hz/ppm kernel (data/README.md). Default to the phantom's value.
    params.a             = gv('a', 137);
    params.tol_a         = gv('tol_a', 0.3);
    params.lambda_r2prime = gv('lambda_r2prime', 0.1);
    params.lambda_chi     = gv('lambda_chi', 10);
    params.lambda_TV      = gv('lambda_TV', 1);

    %% ---- run APART-QSM -------------------------------------------------------------------------
    fprintf('APART: single-orientation separation, %d echoes, a=%.1f Hz/ppm\n', nTE, params.a);
    Res_map = apart_qsm_single_ori(mag_multi_echo, phi_local, r2prime, chimap, params);

    X_para    = Res_map(:,:,:,1);   % χ+ (ppm)
    X_dia_abs = Res_map(:,:,:,2);   % |χ−| (ppm, already a positive magnitude in the reference output)

    %% ---- write canonical artifacts -------------------------------------------------------------
    % χ− ground truth is stored as a POSITIVE magnitude (stages.yml / chisep README); the reference's
    % X_dia_abs is already |χ−|, so take abs() defensively to match the sign convention.
    write_niigz(setimg(mn, single(X_para .* mask)),        fullfile(out, 'chi-para.nii.gz'));  % χ+
    write_niigz(setimg(mn, single(abs(X_dia_abs) .* mask)), fullfile(out, 'chi-dia.nii.gz'));  % χ−
end

function v = getcfg(cfg, name, def)
    if isstruct(cfg) && isfield(cfg, name) && ~isempty(cfg.(name)); v = cfg.(name); else; v = def; end
end
function addpath_env(name, recurse)
    d = getenv(name);
    if ~isempty(d); if recurse; addpath(genpath(d)); else; addpath(d); end; end
end
function nii = setimg(tmpl, img)
    nii = tmpl; nii.img = img;
    nii.hdr.dime.datatype = 16; nii.hdr.dime.bitpix = 32; nii.hdr.dime.dim(1) = 3; nii.hdr.dime.dim(5) = 1;
end
function nii = read_niigz(f)
    t = [tempname '.nii']; system(sprintf('gunzip -c ''%s'' > ''%s''', f, t)); nii = load_untouch_nii(t); delete(t);
end
function write_niigz(nii, f)
    t = [tempname '.nii']; save_untouch_nii(nii, t); system(sprintf('gzip -c ''%s'' > ''%s''', t, f)); delete(t);
end
