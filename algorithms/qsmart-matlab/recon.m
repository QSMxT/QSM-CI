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
% Core_Functions_P (QSM_iLSQR — QSMART calls STI Suite's inversion), and the real Image
% Processing and Statistics toolbox functions they call (compiled from licensed MATLAB; the
% MATLAB Runtime includes their runtime components).
%
% Units: echofit divides the rad/s field by params.ppm (= gyro*B0/1e6) -> tfs in ppm;
% QSMART_SDF multiplies back by params.ppm -> rad/s; QSM_iLSQR with 'TE',1000 (ms, i.e.
% 1 s) undoes gyro*B0 -> chi in ppm; adjust_offset combines in ppm. Same convention as
% the original QSMART.m / Hongfu Sun pipelines — chimap.nii.gz is ppm.
%
% Optional <inp>/config.json overrides (declared in algorithm.yml): frangi_scale_min,
% frangi_scale_max, frangi_scale_ratio, frangi_c, sph_radius_vasculature, fit_threshold.
%
% Optional intermediates (fidelity checks, fidelity/README.md): set QSMCI_INTERMEDIATES to a
% directory, or to 1 for <out>/intermediates. recon then also writes, on the mask grid in
% float64: vasc_only, bothat, vesselness, R_0, tfs (ppm), lfs1/lfs2 (stage-1/2 local field, ppm),
% chi1/chi2 (stage-1/2 chi, ppm) and chimap, plus intermediates.json (Otsu threshold, N4 status).
% Unset (the default), nothing changes.

% Toolbox functions called from STI Suite's .p code, which mcc cannot trace into: name them so
% they are bundled (the rest are traced from the .m code; listing them too is harmless).
%#function graythresh imbothat imclose imdilate imerode imfilter imgaussfilt3 imopen padarray prctile strel

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

    % ---- optional intermediates (absolute path: the toolbox runs in a scratch dir) ----
    idir = getenv('QSMCI_INTERMEDIATES');
    if strcmp(idir, '0'), idir = ''; end
    if strcmp(idir, '1'), idir = fullfile(out, 'intermediates'); end
    if ~isempty(idir)
        if ~startsWith(idir, filesep), idir = fullfile(pwd, idir); end
        if ~exist(idir, 'dir'), mkdir(idir); end
    end

    % ---- inputs ----
    nmask = read_niigz(fullfile(inp, 'mask.nii.gz'));          % header donor for the output
    mask  = double(double(nmask.img) > 0.5);
    ph    = double(getfield(read_niigz(fullfile(inp, 'phase.nii.gz')), 'img'));
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    if ndims(ph) == 3,  ph  = reshape(ph,  [size(ph)  1]); end   % single-echo -> 1-echo 4-D
    if ndims(mag) == 3, mag = reshape(mag, [size(mag) 1]); end

    % The matrix is used as given, as the authors' QSMART.m does: no padding of odd dims
    % (adjust_offset.m and STI's QSM_iLSQR run on odd matrices; padding changed the vessel mask,
    % the Laplacian-unwrapped field and the final chi; astewartau/QSM.rs#320).
    sz0 = size(mask);

    % ---- run in a scratch dir (the toolbox writes NIfTI intermediates to cwd) ----
    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));

    % Generating mask of vasculature (original vasculature_mask, adapted — see
    % vasculature_mask_qsmci.m for the N4/mex packaging changes)
    if isempty(idir)
        vasc_only = vasculature_mask_qsmci(mag, mask, params);
    else
        [vasc_only, vinfo] = vasculature_mask_qsmci(mag, mask, params);
    end

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

    cd(old);
    if ~isempty(idir)
        I = struct('vasc_only', vasc_only, 'bothat', vinfo.bothat, 'vesselness', vinfo.vesselness, ...
                   'R_0', R_0, 'tfs', tfs, 'lfs1', lfs_sdf / params.ppm, 'chi1', chi_iLSQR_1, ...
                   'lfs2', lfs_sdf_2 / params.ppm, 'chi2', chi_iLSQR_2);
        for f = fieldnames(I)'
            write_intermediate(nmask, I.(f{1}), sz0, fullfile(idir, [f{1} '.nii.gz']));
        end
        write_intermediate(nmask, chi, sz0, fullfile(idir, 'chimap.nii.gz'));
        fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
        tb = {'graythresh', 'imbothat', 'imclose', 'imdilate', 'imerode', 'imfilter', ...
              'imgaussfilt3', 'imopen', 'padarray', 'prctile', 'strel'};
        fwrite(fid, jsonencode(struct('otsu_threshold', vinfo.threshold, 'n4', vinfo.n4, ...
            'matlab', version, 'threads', maxNumCompThreads, ...
            'resolved', cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2))));
        fclose(fid);
    end
    % Preserve the input geometry: write through the mask's untouched header (the bundled
    % make_nii/save_nii would lose the affine).
    nmask.img = single(chi);
    nmask.hdr.dime.datatype = 16;  nmask.hdr.dime.bitpix = 32;
    nmask.hdr.dime.dim(1) = 3;  nmask.hdr.dime.dim(5) = 1;
    write_niigz(nmask, fullfile(out, 'chimap.nii.gz'));
    disp('--- Process Finished ---');
end

function write_intermediate(nmask, a, sz0, f)
    a = double(a);
    nmask.img = a(1:sz0(1), 1:sz0(2), 1:sz0(3));
    nmask.hdr.dime.datatype = 64;  nmask.hdr.dime.bitpix = 64;
    nmask.hdr.dime.dim(1) = 3;  nmask.hdr.dime.dim(5) = 1;
    nmask.hdr.dime.scl_slope = 1;  nmask.hdr.dime.scl_inter = 0;
    write_niigz(nmask, f);
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
