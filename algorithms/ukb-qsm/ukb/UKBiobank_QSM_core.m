function [qsm_iLSQR_vsf, mask_vsf] = UKBiobank_QSM_core(phase, mask, TEs, B0, H, voxsz)
% Reconstruction core of UKBiobank_QSM.m, lifted verbatim.
%
% Authors: Chaoyue Wang, Benjamin C. Tendler & Karla L. Miller
% Copyright 2021 University of Oxford, Apache-2.0 (see ukb/UKBiobank_QSM.m.reference)
%
% The upstream script loads DICOM, combines coils (MCPC-3D-S + PRELUDE) and writes to disk.
% QSM-CI supplies already-combined phase and handles IO, so only the reconstruction is kept
% here, with its inputs passed as arguments. Every line below is upstream's except where
% marked "% EDIT:". The two edits are the ones needed to honour the QSM-CI contract:
%
%   1. multi-echo  — upstream hard-codes phase1/phase2; this takes N echoes. At N = 2 the
%                    arithmetic is identical to upstream.
%   2. scaling     — upstream's final `niftiwrite(single(qsm * 1000), ...)` wrote ppb; that
%                    line is IO and is not here, so this returns iLSQR's native ppm.
%
% TEs in ms, B0 in tesla, H the unit B0 direction, voxsz in mm.

    % EDIT (multi-echo): upstream computes maps from phase1 and phase2; use first and last echo.
    phase1 = phase(:,:,:,1);
    phase2 = phase(:,:,:,end);

    map = phasevariance_nonlin_v2(mask, phase1, 2, voxsz);
    map2 = phasevariance_nonlin_v2(mask, phase2, 2, voxsz);
    dim = size(phase1);

    mask(map < 0.6) = 0;
    mask(map2 < 0.5) = 0;

    for ii = 1:dim(3)
        mask(:, :, ii) =  bwareaopen(mask(:, :, ii), 300);
        mask(:, :, ii) =~ bwareaopen(~mask(:, :, ii), 50);
    end
    mask = imfill(mask,26,'holes');
    % phase unwrap
    % EDIT (multi-echo): upstream unwraps phase1 and phase2; unwrap every echo the same way.
    nEcho = size(phase, 4);
    uwphase = zeros(size(phase));
    for e = 1:nEcho
        [uwphase(:,:,:,e), ~] = MRPhaseUnwrap(phase(:,:,:,e), 'voxelsize', voxsz, 'padsize', [64 64 64]);
    end

    T2s = 40;

    % EDIT (multi-echo): upstream forms W1, W2 then (W1*uw1 + W2*uw2)/(W1+W2); same weights, N terms.
    W = TEs(:)' .* exp(-TEs(:)' / T2s);

    phs_comb = zeros(dim);
    for e = 1:nEcho
        phs_comb = phs_comb + W(e) * uwphase(:,:,:,e);
    end
    phs_comb = double(phs_comb / sum(W));

    TE = sum(W .* TEs(:)') / sum(W);

    clear phase1 uwphase W TEs T2s combined phase2 phase uwphase1 uwphase2;
    % v-SHARP and Dipole inversion

    [dB_vsf, mask_vsf]=V_SHARP(phs_comb, mask, 'voxelsize', voxsz, 'smvsize', 12);

    clear mask;

    mask_vsf(map < 0.7) = 0;
    mask_vsf(map2 < 0.6) = 0;

    for ii = 1:dim(3)
        mask_vsf(:, :, ii) = bwareaopen(mask_vsf(:, :, ii), 200);
        mask_vsf(:, :, ii) =~ bwareaopen(~mask_vsf(:, :, ii), 30);
    end
    mask_vsf = imfill(mask_vsf,26,'holes');

    clear map phs_comb map2;

    qsm_iLSQR_vsf = QSM_iLSQR(dB_vsf, mask_vsf, 'TE', TE, 'B0', B0, ...
                'H', H, 'padsize', [64 64 64], ...
                'voxelsize', voxsz);
end
