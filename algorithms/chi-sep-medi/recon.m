function recon(inp, out)
% QSM-CI `chi-separation` stage — χ-separation (MEDI core), SNU-LIST chi-separation toolbox.
% Isolated eval: reads GT local field (ppm) + R2' (Hz) + QSM/chi_total (ppm) + mask + multi-echo
% magnitude, runs chi_sep_MEDI, writes /output/chi-para.nii.gz (χ+) and chi-dia.nii.gz (χ−, |χ−|).
% Same input contract as the iLSQR submission; the difference is the MEDI (morphology-enabled dipole)
% regulariser instead of iLSQR. CSF referencing is disabled (the stage contract provides no CSF mask),
% which mainly affects the χ_total DC that the local field already constrains.
    % Local (full-MATLAB) runs point these env vars at the toolboxes; the compiled MCR binary has them
    % baked in at mcc time (see BUILD.md) and leaves the vars unset, so only addpath when non-empty.
    addpath_env('CHISEP_SHIMS', false);      % padarray/tukeywin/strel shims (no IPT/SPT)
    addpath_env('CHISEP_TOOLBOX', true);     % SNU-LIST chi-separation toolbox
    addpath_env('CHISEP_MEDI', true);        % Cornell MEDI toolbox (chi_sep_MEDI's internal solver)
    addpath_env('CHISEP_NIFTI', false);      % Jimmy Shen NIfTI I/O

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0  = p.B0; CF = 42.5774e6 * B0; b0d = p.B0_dir(:)'; vox = p.voxel_size(:)';

    rd = @(f) double(getfield(read_niigz(fullfile(inp, f)), 'img'));
    localfield = rd('localfield.nii.gz');           % ppm
    r2prime    = rd('r2prime.nii.gz');              % Hz
    qsm        = rd('chimap.nii.gz');               % ppm (chi_total)
    mn         = read_niigz(fullfile(inp, 'mask.nii.gz'));
    mask       = double(mn.img) > 0.5;
    mag4       = rd('magnitude.nii.gz');            % (x,y,z,te)
    mag        = sqrt(sum(mag4.^2, 4));

    local_field_hz = localfield * 1e-6 * CF;        % ppm -> Hz
    N_std = ones(size(mask));
    params.b0_dir = b0d; params.CF = CF; params.voxel_size = vox;
    params.lambda = 1; params.lambda_CSF = 0;       % no CSF mask in the contract -> CSF term off
    option_data.qsm = qsm; option_data.N_std = N_std;
    option_data.mask_CSF = false(size(mask));

    [x_para, x_dia, ~] = chi_sep_MEDI(mag, local_field_hz, r2prime, N_std, mask, params, option_data);

    write_niigz(setimg(mn, single(x_para .* mask)), fullfile(out, 'chi-para.nii.gz'));
    write_niigz(setimg(mn, single(x_dia  .* mask)), fullfile(out, 'chi-dia.nii.gz'));
end
function nii = setimg(tmpl, img)
    nii = tmpl; nii.img = img;
    nii.hdr.dime.datatype = 16; nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3; nii.hdr.dime.dim(5) = 1;
end
function addpath_env(name, recurse)
    d = getenv(name);
    if ~isempty(d)
        if recurse, addpath(genpath(d)); else, addpath(d); end
    end
end
function nii = read_niigz(f)
    t = [tempname '.nii']; system(sprintf('gunzip -c ''%s'' > ''%s''', f, t)); nii = load_untouch_nii(t); delete(t);
end
function write_niigz(nii, f)
    t = [tempname '.nii']; save_untouch_nii(nii, t); system(sprintf('gzip -c ''%s'' > ''%s''', t, f)); delete(t);
end
