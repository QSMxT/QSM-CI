function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB: HEIDI, Homogeneity Enabled Incremental Dipole Inversion (Schweser et al., NeuroImage 2012), the authors' code from qsm_heidi
% (gitlab.com/R01NS114227/qsm_heidi, commit 4592631, which QSM.rs's port cites), run as its
% inversion_heidi.m (after inversion_lsqr.m) runs it, from QSM-CI's inputs.
% Reads <inp>/localfield.nii.gz (ppm) + magnitude (echoes on the 4th axis) + mask + params.json,
% writes <out>/chimap.nii.gz (ppm).
%
% inversion_*.m read their inputs from the pipeline's .mat files (mids objects); recon.m passes the
% same values to the computational cores directly: the local phase (radians) for the SHARP-corrected
% phase, QSM-CI's mask for mask_tissue .* mask_phase .* mask (the masks come from a step not in the
% repository), and the root sum of squares of the echo magnitudes for the magnitude. Every option
% is the one inversion_*.m sets. chi is not masked, as inversion_*.m leave it (0 outside the crop).
%
% HEIDI's gradient mask is denoised first (DEFAULT_GRADIENTMASK_APPLYDENOISING): diffusionimagefilter.m
% runs the ITK executable GradientAnisotropicDiffusionImageFilter the repository ships (ITK 3.20,
% with its libraries), from the folder reppath.m returns. The image installs that folder; BUILD.md.
%
% Bundled: Jimmy Shen NIfTI toolbox and qsm_heidi's heidi/ and lsqr/ (plain .m, plus the ITK executable).
% OS gunzip/gzip (no JVM). Optional <inp>/config.json overrides the parameters in `cfg` below.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, the input
% phase, the LSQR seed (ppm), chi, and intermediates.json (the echo time, the
% phase-to-susceptibility factor, MATLAB version, thread count, where each function resolved).
% Unset, nothing changes.

    cfg = struct('lsqr_tolerance', 1e-5, 'lsqr_max_iter', 400, 'residual_weighting', 0.2, 'cone_threshold', 0.1);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = double(p.voxel_size(:)');
    TE  = double(p.TE(:)');
    B0T = double(p.B0);
    if abs(b0(3)) < 1 - 1e-9
        % generateunitdipoleresponse takes the field direction as the scan's rotation (Options.Rotation,
        % from the DICOM header in the authors' pipeline); recon.m runs B0 along z only.
        error('recon:b0dir', 'B0_dir %s: this recon supports B0 along z only', mat2str(b0));
    end

    nlf   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(nlf.img);                                                % local field, ppm
    Mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));   % echoes on dim 4
    magnitude = sqrt(sum(mag.^2, 4));                                       % QSMxT's combined magnitude (RSS)

    % The authors' units: the local phase in radians at the last echo time (TE in ms), rotating-frame
    % sign (phase2susceptibilityfactor.m's default), so chi = -x * phase2susceptibilityfactor * 1e6.
    Options = struct();
    Options.echoTime = TE(end) * 1e3;                                       % ms; the last echo (L70-71)
    % The pipeline's Options.Rotation is the scan orientation from the DICOM header; an axial scan's is
    % no rotation (angle 0). It must be given: without it the cores use SEPIA's k-space DipoleKernel
    % instead of generateunitdipoleresponse's spatial-domain dipole that inversion_*.m select.
    Options.Rotation = struct('angle', 0, 'axis', [0 0 1]);
    Options.magneticFieldStrength = B0T;
    Options.voxelAspectRatio = vox;
    C = getconstants();
    phase = -field * 1e-6 * C.gyromagneticRatio * B0T * TE(end);

    % inversion_*.m: crop to the mask's bounding box, then the 40-voxel anti-aliasing frame.
    DEFAULT_ANTIALIASINGFRAMEWIDTH = 40;
    % inversion_*.m call zealouscrop(mask) with no frame value, so it takes the value to crop from the
    % mask's edge rows: a mask with no zero border (e.g. a box inside the brain) has only "uniform"
    % all-1 slices and is cropped to 1x1. Frame value 0, as the authors' prepareforconvolution.m crops a
    % mask (zealouscrop(mask,[],0)), removes only all-0 slices: the same crop whenever the mask has zero
    % background at the edge (every full-FOV brain mask), and no crop when it has none. BUILD.md.
    [suscCompMask, zcInfo] = zealouscrop(Mask, [], 0);
    [suscCompMask, pcInfo] = prepareforconvolution(suscCompMask, [], DEFAULT_ANTIALIASINGFRAMEWIDTH);
    magnitude = zealouscrop(magnitude, zcInfo);
    magnitude = prepareforconvolution(magnitude, [], DEFAULT_ANTIALIASINGFRAMEWIDTH);
    phase = zealouscrop(phase, zcInfo);
    phase = prepareforconvolution(phase, [], DEFAULT_ANTIALIASINGFRAMEWIDTH);

    % inversion_lsqr.m's Options.
    OL = Options;
    OL.tolerance = double(cfg.lsqr_tolerance);
    OL.maxit = double(cfg.lsqr_max_iter);
    OL.offsetUseBool = true;
    OL.isFourierDomainFormula = false;
    OL.TikhonovRegularizationSusceptibility = [];
    OL.solvingType = [];
    OL.DipoleFilter = [];
    OL.residualWeighting = double(cfg.residual_weighting) / 9.4 * B0T;      % 0.2 optimal in QUASAR paper
    [susceptibilityRaw, ~, residual] = computesusceptibility_lsqr(phase, OL, logical(suscCompMask), [], magnitude);
    factor = phase2susceptibilityfactor([], Options);

    % inversion_heidi.m's Options; its seed is the LSQR result before the unit conversion
    % (inversion_lsqr.mat's susceptibilityRaw), on the same grid.
    OH = Options;
    OH.isFourierDomainFormula = false;
    OH.TikhonovRegularizationSusceptibility = [];
    OH.solvingType = [];
    OH.DipoleFilter = [];
    OH.useHEIDI = true;
    OH.PostProcCone.threshold = double(cfg.cone_threshold);
    OH.PostProcCone.tol = eps;
    OH.PostProcCone.tolEnergy = eps;
    susceptibility = computesusceptibility_heidi(susceptibilityRaw, phase, OH, logical(suscCompMask), [], magnitude);
    chi = -susceptibility .* factor * 1e6;
    chi = uncrop(chi, pcInfo, zcInfo);

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nlf, uncrop(phase, pcInfo, zcInfo), fullfile(idir, 'phase_input.nii.gz'));
        write_intermediate(nlf, uncrop(-susceptibilityRaw .* factor * 1e6, pcInfo, zcInfo), fullfile(idir, 'chi_lsqr.nii.gz'));
        write_intermediate(nlf, chi, fullfile(idir, 'chimap_f64.nii.gz'));
        write_meta(idir, struct('echoTime_ms', Options.echoTime, 'factor', factor, 'cfg', cfg, ...
            'itk_dir', reppath));
    end

    nlf.img = single(chi);
    nlf.hdr.dime.datatype = 16;  nlf.hdr.dime.bitpix = 32;
    nlf.hdr.dime.dim(1) = 3;  nlf.hdr.dime.dim(5) = 1;
    nlf.hdr.dime.scl_slope = 1;  nlf.hdr.dime.scl_inter = 0;
    write_niigz(nlf, fullfile(out, 'chimap.nii.gz'));
    % computesusceptibility_lsqr.m ends with an unconditional `figure; plot(...)` of LSQR's residual
    % history. A compiled binary does not exit while a figure is open (it waited until the job's time
    % limit), so close it once chimap is written. Licensed MATLAB -batch exits either way.
    close all force;
end

function a = uncrop(a, pcInfo, zcInfo)
% inversion_*.m: undo prepareforconvolution and zealouscrop.
    a = prepareforconvolution(a, [], [], pcInfo);
    a = zealouscrop(a, zcInfo, [], true);
end

function nii = read_niigz(f)
    t = [tempname '.nii'];
    system(sprintf('gunzip -c ''%s'' > ''%s''', f, t));
    nii = load_untouch_nii(t);
    delete(t);
    % load_untouch_nii returns the stored values: apply scl_slope/scl_inter where set.
    s = double(nii.hdr.dime.scl_slope); o = double(nii.hdr.dime.scl_inter);
    if s ~= 0 && ~(s == 1 && o == 0)
        nii.img = double(nii.img) * s + o;
        nii.hdr.dime.scl_slope = 1;  nii.hdr.dime.scl_inter = 0;
    end
end

function write_niigz(nii, f)
    t = [tempname '.nii'];
    save_untouch_nii(nii, t);
    system(sprintf('gzip -c ''%s'' > ''%s''', t, f));
    delete(t);
end

function tb = toolbox_functions()
    tb = {'computesusceptibility_heidi', 'computesusceptibility_lsqr', 'Core_Nesterov_fs', 'diffusionimagefilter', 'reppath', 'generateunitdipoleresponse', 'discretegradient', 'zealouscrop', 'prepareforconvolution', 'phase2susceptibilityfactor', 'write_nii', 'load_nii_raw', 'lsqr'};
end

function idir = intermediates_dir(out)
% QSMCI_INTERMEDIATES: a directory, or 1 for <out>/intermediates. Unset or 0: none.
    idir = getenv('QSMCI_INTERMEDIATES');
    if strcmp(idir, '0'), idir = ''; end
    if strcmp(idir, '1'), idir = fullfile(out, 'intermediates'); end
    if isempty(idir), return; end
    if ~startsWith(idir, filesep), idir = fullfile(pwd, idir); end
    if ~exist(idir, 'dir'), mkdir(idir); end
end

function write_intermediate(tmpl, a, f)
% One intermediate as float64 NIfTI, through the input's untouched header (affine preserved).
    a = double(a);
    tmpl.img = a;
    tmpl.hdr.dime.datatype = 64;  tmpl.hdr.dime.bitpix = 64;
    tmpl.hdr.dime.dim(1) = max(3, ndims(a));
    tmpl.hdr.dime.dim(2:5) = [size(a, 1) size(a, 2) size(a, 3) size(a, 4)];
    tmpl.hdr.dime.scl_slope = 1;  tmpl.hdr.dime.scl_inter = 0;
    write_niigz(tmpl, f);
end

function write_meta(idir, m)
% intermediates.json: M plus the MATLAB version, the thread count, and where each function resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
