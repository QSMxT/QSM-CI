function recon(inp, out)
% QSM-CI `end-to-end` stage — the UK Biobank QSM pipeline.
%
% Reproduces UKBiobank_QSM.m (Chaoyue Wang, Benjamin C. Tendler & Karla L. Miller,
% University of Oxford, Apache-2.0) from the point where combined phase exists:
% phase-variance masking, Laplacian unwrapping, T2*-weighted echo combination,
% V-SHARP background removal and iLSQR dipole inversion.
%
% Reads  <inp>/phase.nii.gz (radians, 4D x,y,z,echo), magnitude.nii.gz, mask.nii.gz, params.json
% Writes <out>/chimap.nii.gz in **ppm**. Note the original writes ppb (it scales by 1000);
% the QSM-CI artifact contract is ppm, so that scaling is deliberately not applied here.
%
% Coil combination (MCPC-3D-S, with PRELUDE unwrapping the Hermitian inner product) is
% upstream of this stage: QSM-CI supplies already-combined phase, so it is not reproduced.
%
% Optional <inp>/config.json overrides {t2star_ms, smvsize, padsize, mask_refine}.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    H   = p.B0_dir(:)'; H = H / norm(H);
    vox = p.voxel_size(:)';
    B0  = p.B0;                                  % Tesla
    TEs = p.TE(:)' * 1000;                       % seconds -> ms (STI Suite works in ms,
                                                 % and the UKB T2* constant is in ms)

    cfg = struct('t2star_ms', 40, 'smvsize', 12, 'padsize', 64, 'mask_refine', true);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end
    ps = double(cfg.padsize); padsize = [ps ps ps];

    nii   = read_niigz(fullfile(inp, 'phase.nii.gz'));
    phase = double(nii.img);                                        % radians
    mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;
    if size(phase, 4) ~= numel(TEs)
        error('recon: %d phase volumes but %d echo times', size(phase, 4), numel(TEs));
    end
    nEcho = numel(TEs);
    dim   = size(mask);

    % ---- phase-variance reliability maps -------------------------------------------------
    % UKB computes one per echo and uses them twice, with tightening thresholds: first to
    % trim the input mask, then again after V-SHARP. With two echoes the thresholds are
    % (0.6, 0.5) and (0.7, 0.6); generalised here as a first/second pair applied to the
    % first and last echo, which reduces to the original for the two-echo case.
    maps = cell(1, nEcho);
    if cfg.mask_refine
        for e = 1:nEcho
            maps{e} = phasevariance_nonlin_v2(mask, phase(:,:,:,e), 2, vox);
        end
        mask = trim_mask(mask, maps{1}, maps{end}, 0.6, 0.5, 300, 50, dim);
    end

    % ---- Laplacian unwrapping, per echo --------------------------------------------------
    uw = zeros(size(phase));
    for e = 1:nEcho
        [uw(:,:,:,e), ~] = MRPhaseUnwrap(phase(:,:,:,e), 'voxelsize', vox, 'padsize', padsize);
    end

    % ---- T2*-weighted echo combination ---------------------------------------------------
    % W_i = TE_i * exp(-TE_i / T2*): the SNR-optimal weighting for a mono-exponential decay.
    T2s = double(cfg.t2star_ms);
    W   = TEs .* exp(-TEs / T2s);
    phs_comb = zeros(dim);
    for e = 1:nEcho
        phs_comb = phs_comb + W(e) * uw(:,:,:,e);
    end
    phs_comb = phs_comb / sum(W);
    TE_eff   = sum(W .* TEs) / sum(W);                              % ms

    clear uw phase;

    % ---- V-SHARP background field removal ------------------------------------------------
    [dB_vsf, mask_vsf] = V_SHARP(phs_comb, mask, 'voxelsize', vox, ...
                                 'smvsize', double(cfg.smvsize));

    if cfg.mask_refine
        mask_vsf = trim_mask(mask_vsf > 0.5, maps{1}, maps{end}, 0.7, 0.6, 200, 30, dim);
    end

    % ---- iLSQR dipole inversion ----------------------------------------------------------
    chi = QSM_iLSQR(dB_vsf, double(mask_vsf), 'TE', TE_eff, 'B0', B0, 'H', H, ...
                    'padsize', padsize, 'voxelsize', vox);          % ppm
    chi = double(chi) .* double(mask_vsf);

    nii.img = single(chi);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3;  nii.hdr.dime.dim(5) = 1;
    write_niigz(nii, fullfile(out, 'chimap.nii.gz'));
end

function m = trim_mask(m, map1, map2, t1, t2, keepArea, fillArea, dim)
% UKB mask cleanup: drop voxels whose phase is unreliable, remove small 2-D specks
% slice by slice, close small 2-D gaps, then fill 3-D holes.
    m = logical(m);
    m(map1 < t1) = false;
    m(map2 < t2) = false;
    for ii = 1:dim(3)
        m(:,:,ii) = bwareaopen(m(:,:,ii), keepArea);
        m(:,:,ii) = ~bwareaopen(~m(:,:,ii), fillArea);
    end
    m = imfill(m, 26, 'holes');
end
