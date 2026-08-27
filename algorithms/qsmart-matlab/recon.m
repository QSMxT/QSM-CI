function recon(inp, out)
% QSM-CI `end-to-end` span in MATLAB — QSMART v1.0, the AUTHORS' ORIGINAL toolbox
% (Yaghmaie et al., NeuroImage 2021; github.com/wtsyeda/QSMART). Reads
% <inp>/phase.nii.gz (radians, 4-D) + magnitude + mask + params.json and runs the
% original pipeline from QSMART.m:
%
%   vasculature_mask -> unwrap_phase (laplacian) -> echofit (yields the R_0
%   reliability mask) -> QSMART_SDF stage 1 -> QSM_iLSQR -> QSMART_SDF stage 2
%   -> QSM_iLSQR -> adjust_offset  =>  <out>/chimap.nii.gz (ppm)
%
% Skipped vs. QSMART.m (QSM-CI supplies these): readComplexDicoms + coil_comb (inputs
% are already coil-combined 4-D NIfTIs) and brainmask/BET (the contract mask.nii.gz is
% used, for comparability across submissions).
%
% Bundled at build time (see BUILD.md): QSMART toolbox .m files, Jimmy Shen NIfTI
% toolbox, frangi_filter_version2a (+ precompiled eig3volume/imgaussian mex),
% curvatures.m (File Exchange), lapunwrap.m (Hongfu Sun, MIT), STI Suite v3
% Core_Functions_P (QSM_iLSQR — QSMART calls STI Suite's inversion), and shims/ (IPT +
% Statistics toolbox replacements; the MATLAB build here has neither toolbox).
%
% Units: echofit divides the rad/s field by params.ppm (= gyro*B0/1e6) -> tfs in ppm;
% QSMART_SDF multiplies back by params.ppm -> rad/s; QSM_iLSQR with 'TE',1000 (ms, i.e.
% 1 s) undoes gyro*B0 -> chi in ppm; adjust_offset combines in ppm. Same convention as
% the original QSMART.m / Hongfu Sun pipelines — chimap.nii.gz is ppm.
%
% Optional <inp>/config.json overrides (declared in algorithm.yml): frangi_scale_min,
% frangi_scale_max, frangi_scale_ratio, frangi_c, sph_radius_vasculature, fit_threshold.

    % ---- acquisition parameters (CONTRACT.md params.json) ----
    p      = jsondecode(fileread(fullfile(inp, 'params.json')));
    z_prjs = p.B0_dir(:)'; z_prjs = z_prjs / norm(z_prjs);
    vox    = double(p.voxel_size(:)');
    TE     = double(p.TE(:)');                 % seconds

    % ---- QSMART parameter struct (Demo_QSMART.m defaults, human scan) ----
    params.species          = 'human';
    params.field            = double(p.B0);    % Tesla (from params.json)
    params.gyro             = 2.675e8;         % rad/s/T proton gyromagnetic ratio
    params.ppm              = (params.gyro * params.field) / 1e6;   % rad/s per ppm
    params.ph_unwrap_method = 'laplacian';
    % thresholds / vasculature
    params.sph_radius_vasculature = 8;
    params.adaptive_threshold     = 0;
    % Frangi filter
    params.frangi_scaleRange = [0.5 6];
    params.frangi_scaleRatio = 0.5;
    params.frangi_C          = 500;
    % multi-echo fit
    params.fit_threshold     = 40;
    % spatially-dependent filtering (background removal)
    params.sdf_sp_radius     = 8;
    params.s1.sdf_sigma1     = 10;  params.s1.sdf_sigma2 = 0;
    params.s2.sdf_sigma1     = 8;   params.s2.sdf_sigma2 = 2;
    params.sdffilterLowerLim = 0.6;
    params.sdffilterCurvConstant = 500;
    % Demo_QSMART.m's mag_threshold/sph_radius1 are consumed only by brainmask.m (BET),
    % which QSM-CI skips (the contract mask is used), so they are not set here.
    params.iminfo.resolution  = vox;
    params.iminfo.echo_times  = TE;            % seconds (matches readComplexDicoms)
    params.iminfo.z_prjs      = z_prjs;

    % ---- config.json overrides ----
    cfg = struct('frangi_scale_min', params.frangi_scaleRange(1), ...
                 'frangi_scale_max', params.frangi_scaleRange(2), ...
                 'frangi_scale_ratio', params.frangi_scaleRatio, ...
                 'frangi_c', params.frangi_C, ...
                 'sph_radius_vasculature', params.sph_radius_vasculature, ...
                 'fit_threshold', params.fit_threshold);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end
    params.frangi_scaleRange      = [double(cfg.frangi_scale_min) double(cfg.frangi_scale_max)];
    params.frangi_scaleRatio      = double(cfg.frangi_scale_ratio);
    params.frangi_C               = double(cfg.frangi_c);
    params.sph_radius_vasculature = double(cfg.sph_radius_vasculature);
    params.fit_threshold          = double(cfg.fit_threshold);

    % ---- inputs ----
    nmask = read_niigz(fullfile(inp, 'mask.nii.gz'));          % header donor for the output
    mask  = double(double(nmask.img) > 0.5);
    ph    = double(getfield(read_niigz(fullfile(inp, 'phase.nii.gz')), 'img'));
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    if ndims(ph) == 3,  ph  = reshape(ph,  [size(ph)  1]); end   % single-echo -> 1-echo 4-D
    if ndims(mag) == 3, mag = reshape(mag, [size(mag) 1]); end

    % QSMART/STI assume even matrix dims (adjust_offset's -N/2:N/2-1 k-grid, STI's
    % calcD2Matrix). Zero-pad odd dims to even (post) and crop back at the end.
    sz0 = size(mask); po = mod(sz0, 2);
    ph   = padarray(ph,   po, 0, 'post');
    mag  = padarray(mag,  po, 0, 'post');
    mask = padarray(mask, po, 0, 'post');

    % ---- run in a scratch dir (the toolbox writes NIfTI intermediates to cwd) ----
    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));

    % Generating mask of vasculature (original vasculature_mask, adapted — see
    % vasculature_mask_qsmci.m for the N4/mex packaging changes)
    vasc_only = vasculature_mask_qsmci(mag, mask, params);

    % Phase unwrapping (original unwrap_phase, laplacian method -> lapunwrap)
    unph = unwrap_phase(ph, mask, params.iminfo.resolution, params.ph_unwrap_method);

    % Echo fit — magnitude-weighted LS fit of phase to TE; R_0 = reliability mask
    disp('--> magnitude weighted LS fit of phase to TE ...');
    [tfs, R_0] = echofit(unph, mag, 0, params);

    % Cleaning the total field shift to find the local field shift (stage 1)
    lfs_sdf = QSMART_SDF(tfs, mask, R_0, [], 1, params);

    disp('---running QSM inversion step 1---');
    chi_iLSQR_1 = QSM_iLSQR(lfs_sdf, mask.*R_0, 'H', z_prjs, 'voxelsize', params.iminfo.resolution, ...
                  'niter', 50, 'TE', 1000, 'B0', params.field);

    disp('---running QSM inversion step 2---');
    lfs_sdf_2 = QSMART_SDF(tfs, mask, R_0, vasc_only, 2, params);
    chi_iLSQR_2 = QSM_iLSQR(lfs_sdf_2, mask.*vasc_only.*R_0, 'H', z_prjs, 'voxelsize', params.iminfo.resolution, ...
                  'niter', 50, 'TE', 1000, 'B0', params.field);

    % Combining 2-stage chi maps (returns the offset-adjusted combined map, ppm)
    chi = adjust_offset(mask.*R_0 - vasc_only, lfs_sdf, double(chi_iLSQR_1), double(chi_iLSQR_2), params);
    chi = double(chi) .* mask;
    chi = chi(1:sz0(1), 1:sz0(2), 1:sz0(3));   % crop the even-dim padding

    cd(old);
    % Preserve the input geometry: write through the mask's untouched header (the bundled
    % make_nii/save_nii would lose the affine).
    nmask.img = single(chi);
    nmask.hdr.dime.datatype = 16;  nmask.hdr.dime.bitpix = 32;
    nmask.hdr.dime.dim(1) = 3;  nmask.hdr.dime.dim(5) = 1;
    write_niigz(nmask, fullfile(out, 'chimap.nii.gz'));
    disp('--- Process Finished ---');
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
