function recon(inp, out)
% QSM-CI `chi-separation` stage — χ-separation (MEDI core), SNU-LIST chi-separation toolbox.
% Isolated eval: reads GT local field (ppm) + R2' (Hz) + QSM/chi_total (ppm) + mask + multi-echo
% magnitude, runs chi_sep_MEDI, writes /output/chi-para.nii.gz (χ+) and chi-dia.nii.gz (χ−, |χ−|).
% Same input contract as the iLSQR submission; the difference is the MEDI (morphology-enabled dipole)
% regulariser instead of iLSQR. CSF referencing is disabled (the stage contract provides no CSF mask),
% which mainly affects the χ_total DC that the local field already constrains.
%
% Bundled at build time (BUILD.md): Jimmy Shen NIfTI toolbox, the Cornell MEDI toolbox (2024.11.26),
% the χ-separation toolbox (pcode), and the real Image Processing and Signal Processing toolbox
% functions they call (compiled from licensed MATLAB; the MATLAB Runtime includes their runtime
% components).
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64: the local
% field in Hz and chi_sep_MEDI's third output, plus intermediates.json (MATLAB version, thread count,
% and where each toolbox function resolved). Unset (the default), nothing changes.

% Toolbox functions the pcode calls, which mcc can't trace into: name them so they are bundled.
% Found by profiling a licensed run (../../fidelity/matlab/README.md, `trace`); keep
% toolbox_functions() below in step.
%#function hann hanning imclose imdilate imerode imopen padarray strel tukeywin

    % Local (full-MATLAB) runs point these env vars at the toolboxes; the compiled MCR binary has them
    % baked in at mcc time (see BUILD.md) and leaves the vars unset, so only addpath when non-empty.
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

    % Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json (absent otherwise).
    cfg = struct();
    if isfile(fullfile(inp, 'config.json')); cfg = jsondecode(fileread(fullfile(inp, 'config.json'))); end
    if isfield(cfg, 'lambda'); lambda = cfg.lambda; else; lambda = 1; end

    local_field_hz = localfield * 1e-6 * CF;        % ppm -> Hz
    N_std = ones(size(mask));
    params.b0_dir = b0d; params.CF = CF; params.voxel_size = vox;
    params.lambda = lambda; params.lambda_CSF = 0;  % no CSF mask in the contract -> CSF term off
    option_data.qsm = qsm; option_data.N_std = N_std;
    option_data.mask_CSF = false(size(mask));

    [x_para, x_dia, x_tot] = chi_sep_MEDI(mag, local_field_hz, r2prime, N_std, mask, params, option_data);

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(mn, local_field_hz, fullfile(idir, 'local_field_hz.nii.gz'));
        write_intermediate(mn, x_tot, fullfile(idir, 'x_tot.nii.gz'));
        write_meta(idir, struct());
    end

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

function tb = toolbox_functions()
    tb = {'hann', 'hanning', 'imclose', 'imdilate', 'imerode', 'imopen', 'padarray', 'strel', 'tukeywin'};
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
% intermediates.json: M plus the MATLAB version, the thread count, and where each toolbox
% function in the %#function pragma resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
