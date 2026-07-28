function recon(inp, out)
% QSM-CI `chi-separation` stage — χ-separation (iLSQR core), SNU-LIST chi-separation toolbox.
% Isolated eval: reads local field (ppm) + R2' (Hz) + mask + multi-echo magnitude, runs chi_sep_iLSQR,
% writes /output/chi-para.nii.gz (χ+) and chi-dia.nii.gz (χ−, stored as |χ−|).
%
% IMPORTANT (Bunya diagnostic, 2026-07-28): chi_sep_iLSQR must be fed a QSM produced by STI-Suite's own
% QSM_iLSQR — NOT an externally supplied χ_total. Feeding the phantom's GT chimap gives a near-artifact
% result (χ+ xsim 0.22); reconstructing the QSM in-house with STI-Suite QSM_iLSQR from the same local
% field (matching the toolbox's scaling/orientation conventions) gives a real reconstruction (χ+ xsim
% 0.49, χ− 0.32) and ~70x lower cross-source leakage. So we ignore chimap.nii.gz and derive the QSM here.
    addpath(getenv('CHISEP_SHIMS'));                              % padarray/tukeywin/strel shims (no IPT/SPT)
    addpath(genpath(getenv('CHISEP_TOOLBOX')));                  % SNU-LIST chi-separation toolbox
    addpath(genpath(getenv('CHISEP_STISUITE')));                % STI Suite (QSM_iLSQR)
    addpath(getenv('CHISEP_NIFTI'));                            % Jimmy Shen NIfTI I/O

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0  = p.B0; CF = 42.5774e6 * B0; b0d = p.B0_dir(:)'; vox = p.voxel_size(:)';
    dTE = p.TE(2) - p.TE(1);                         % echo spacing (s)

    rd = @(f) double(getfield(read_niigz(fullfile(inp, f)), 'img'));
    localfield = rd('localfield.nii.gz');           % ppm
    r2prime    = rd('r2prime.nii.gz');              % Hz
    mn         = read_niigz(fullfile(inp, 'mask.nii.gz'));
    mask       = double(mn.img) > 0.5;
    mag4       = rd('magnitude.nii.gz');            % (x,y,z,te)
    mag        = sqrt(sum(mag4.^2, 4));

    local_field_hz = localfield * 1e-6 * CF;        % ppm -> Hz (chi_sep_iLSQR expects Hz)
    params.b0_dir = b0d; params.CF = CF; params.voxel_size = vox;

    % --- reconstruct the QSM in-house with STI-Suite QSM_iLSQR (see note above) ---
    tissue_phase = local_field_hz * 2*pi * dTE;     % Hz -> radian tissue phase over one echo spacing
    qsm = QSM_iLSQR(tissue_phase, mask, 'TE', dTE*1e3, 'B0', B0, 'H', b0d, ...
                    'padsize', [12 12 12], 'voxelsize', vox);

    % noise weighting from magnitude (~1 in tissue, higher where signal is low); CSF from mask edge is
    % not available in isolated eval, so N_std alone. (CSF mask + N_std had no measurable effect vs the
    % QSM-input fix in the diagnostic, so we keep this minimal.)
    N_std = mean(mag(mask)) ./ max(mag, eps); N_std(~mask) = 0;
    option_data.qsm = qsm; option_data.N_std = N_std;

    [x_para, x_dia, ~] = chi_sep_iLSQR(mag, local_field_hz, r2prime, mask, params, option_data);

    write_niigz(setimg(mn, single(x_para .* mask)), fullfile(out, 'chi-para.nii.gz'));
    write_niigz(setimg(mn, single(x_dia  .* mask)), fullfile(out, 'chi-dia.nii.gz'));
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
