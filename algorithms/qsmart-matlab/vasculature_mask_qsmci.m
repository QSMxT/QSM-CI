function vasc_only = vasculature_mask_qsmci(mag_corr, mask, params)
% QSM-CI adaptation of QSMART_toolbox_v1.0/vasculature_mask.m (Yaghmaie et al.,
% NeuroImage 2021; toolbox by Warda Syeda, Melbourne Brain Centre Imaging Unit).
% The science is unchanged: mean-echo magnitude -> N4 bias correction -> spherical
% bottom-hat -> Frangi vesselness -> Otsu threshold -> inverted vessel mask
% (vessels = 0, rest of the brain = 1).
%
% Changes for QSM-CI packaging only:
%  1. N4BiasFieldCorrection is invoked directly if present on PATH (the original ran
%     `module load ants/1.9.v4; N4BiasFieldCorrection ...` on an HPC). The container
%     image bakes ANTs' N4 in (see Dockerfile/BUILD.md). If the binary is missing
%     (e.g. a plain-MATLAB local run), the bias-correction step is SKIPPED with a
%     warning and the raw mean-echo magnitude is used — acceptable on simulated
%     bias-free data, but for faithful in-vivo behaviour keep N4 in the image.
%  2. The eig3volume mex used by FrangiFilter3D is compiled at BUILD time (the original
%     ran `mex eig3volume.c` at run time, which a deployed MATLAB Runtime cannot do).
%  3. Debug NIfTI intermediates (test.nii, enhanced.nii, vasc_only.nii) are not written.

vox = params.iminfo.resolution;
imsize = size(mag_corr);

disp('---generating vasculature mask---');
AvgEcho = mean(mag_corr, 4);

% N4 bias correction of the mean-echo magnitude (original behaviour), if available.
[n4_missing, ~] = system('command -v N4BiasFieldCorrection > /dev/null 2>&1');
if n4_missing == 0
    nii = make_nii(AvgEcho, vox);
    save_nii(nii, 'AvgEcho.nii');
    st = system('N4BiasFieldCorrection -i AvgEcho.nii -o AvgEcho_n4.nii');
    if st == 0
        nii = load_nii('AvgEcho_n4.nii');
        AvgEcho_n4 = double(nii.img);
    else
        warning('N4BiasFieldCorrection failed (exit %d); using the uncorrected mean-echo magnitude.', st);
        AvgEcho_n4 = AvgEcho;
    end
else
    warning(['N4BiasFieldCorrection not found on PATH; skipping the bias-correction ', ...
             'of the mean-echo magnitude (the original QSMART applies ANTs N4 here).']);
    AvgEcho_n4 = AvgEcho;
end

% Bottom-hat with a spherical structuring element highlights dark tubular structures.
SE = strel('sphere', params.sph_radius_vasculature);
test = imbothat(AvgEcho_n4, SE);

% Frangi vesselness (bundled frangi_filter_version2a; eig3volume mex precompiled).
vasc_only = zeros(imsize(1:3));
options = struct('FrangiScaleRange', params.frangi_scaleRange, ...
                 'FrangiScaleRatio', params.frangi_scaleRatio, ...
                 'FrangiAlpha', 0.5, 'FrangiBeta', 0.5, 'FrangiC', params.frangi_C, ...
                 'verbose', true, 'BlackWhite', false);
enhanced = FrangiFilter3D(test .* mask, options);

% Otsu's thresholding, then invert: vessels -> 0, everything else -> 1.
T = graythresh(enhanced);
vasc_only(enhanced > T) = 1;
vasc_only(find(~mask)) = 0;
vasc_only = double(~vasc_only);
end
