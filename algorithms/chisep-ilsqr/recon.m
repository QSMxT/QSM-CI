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
%
% Bundled at build time (BUILD.md): Jimmy Shen NIfTI toolbox, STI Suite v3 Core_Functions_P and the
% χ-separation toolbox (both pcode), and the real Image Processing and Signal Processing toolbox
% functions they call (compiled from licensed MATLAB; the MATLAB Runtime includes their runtime
% components).
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64: the in-house
% QSM, the noise weighting N_std, the local field in Hz, and chi_sep_iLSQR's third output, plus
% intermediates.json (MATLAB version, thread count, and where each toolbox function resolved).
% Unset (the default), nothing changes.

% Toolbox functions the pcode calls, which mcc can't trace into: name them so they are bundled.
% Found by profiling a licensed run (../../fidelity/matlab/README.md, `trace`); keep
% toolbox_functions() below in step.
%#function hann hanning imclose imdilate imerode imopen padarray strel tukeywin

    % Local (full-MATLAB) runs point these env vars at the toolboxes; the compiled MCR binary has them
    % baked in at mcc time (see BUILD.md) and leaves the vars unset, so only addpath when non-empty.
    addpath_env('CHISEP_TOOLBOX', true);     % SNU-LIST chi-separation toolbox
    addpath_env('CHISEP_STISUITE', true);    % STI Suite (QSM_iLSQR)
    addpath_env('CHISEP_NIFTI', false);      % Jimmy Shen NIfTI I/O

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

    % Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json (absent otherwise).
    cfg = struct();
    if isfile(fullfile(inp, 'config.json')); cfg = jsondecode(fileread(fullfile(inp, 'config.json'))); end
    if isfield(cfg, 'pad_size'); ps = cfg.pad_size; else; ps = 12; end

    % --- reconstruct the QSM in-house with STI-Suite QSM_iLSQR (see note above) ---
    tissue_phase = local_field_hz * 2*pi * dTE;     % Hz -> radian tissue phase over one echo spacing
    qsm = QSM_iLSQR(tissue_phase, mask, 'TE', dTE*1e3, 'B0', B0, 'H', b0d, ...
                    'padsize', [ps ps ps], 'voxelsize', vox);

    % noise weighting from magnitude (~1 in tissue, higher where signal is low); CSF from mask edge is
    % not available in isolated eval, so N_std alone. (CSF mask + N_std had no measurable effect vs the
    % QSM-input fix in the diagnostic, so we keep this minimal.)
    N_std = mean(mag(mask)) ./ max(mag, eps); N_std(~mask) = 0;
    option_data.qsm = qsm; option_data.N_std = N_std;

    [x_para, x_dia, x_tot] = chi_sep_iLSQR(mag, local_field_hz, r2prime, mask, params, option_data);

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(mn, qsm, fullfile(idir, 'qsm.nii.gz'));
        write_intermediate(mn, N_std, fullfile(idir, 'n_std.nii.gz'));
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
