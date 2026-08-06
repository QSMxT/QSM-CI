function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB — mSMV (Maximum Spherical Mean Value), Roberts et al., MRM 2024.
%
% Reads  <inp>/totalfield.nii.gz (ppm) + mask + params.json,
% writes <out>/localfield.nii.gz (ppm) on the input affine.
%
% ---- What mSMV is, and how it maps to the `bfr` stage ---------------------------------------------
% mSMV is fundamentally a residual-shadow REMOVER: it samples and removes the residual harmonic
% background field near the brain boundary (via the maximum-value corollary of Green's theorem),
% preserving the edge of the brain WITHOUT erosion. In the paper/repo it is normally run as a
% REFINEMENT after a primary background-field removal (PDF/VSHARP/LBV/SHARP).
%
% BUT the upstream `msmv()` function (mSMV/code/mSMV_functions/msmv.m) has a `prefilter` flag: with
% prefilter=1 (its default) it FIRST performs a Spherical-Mean-Value primary removal, RDF-SMV(RDF),
% and THEN the mSMV boundary correction. SMV (spherical mean value, radius `radius` mm) IS a complete
% harmonic background-field removal in its own right. So mSMV(prefilter=1) run on a total field is a
% self-contained total->local BFR = [SMV primary removal] + [mSMV boundary shadow correction]. That is
% exactly the standalone composition we package here (documented as "SMV + mSMV" in algorithm.yml/README).
% We therefore call the upstream function with prefilter=1 and do NOT prepend a separate BFR.
%
% ---- Units -----------------------------------------------------------------------------------------
% mSMV (like MEDI's RDF) operates on the field in RADIANS: its shadow-detection threshold is capped at
% 0.01*B0/3 radians (see kernel_lim.m). Our contract carries the field in ppm, so we convert
%   radians = field_ppm * 1e-6 * (2*pi * gyro * B0) * TE
% run mSMV, then convert the filtered field back to ppm with the same factor. mSMV is (bar the
% thresholded steps) a linear high-pass filter, so the ppm result is scale-invariant in the linear
% limit; TE only sets the operating point of the radian threshold. `simulated_TE` is exposed as a
% parameter with a MEDI-representative default.
%
% ---- Vessel mask -----------------------------------------------------------------------------------
% mSMV's optional vessel-protection step needs an R2* map (via `fibermetric`), which the `bfr` stage
% does not provide. Upstream README: "if this variable is missing... this step will be skipped." We
% pass an all-zero R2* so the Frangi vessel mask is empty (no voxels protected as vessels) — the
% documented no-R2* behaviour.
%
% Bundled: OS gunzip/gzip NIfTI I/O (no JVM); upstream mSMV `code/` + MEDI SMV helpers baked in by mcc;
% IPT `imbinarize` shim (`shims/`). See BUILD.md.

    % Uncompiled (local) runs put the vendored deps on the path; the compiled MCR binary bakes them
    % in at mcc time and leaves the folders absent, so only addpath when the folder exists / undeployed.
    if ~isdeployed
        here = fileparts(mfilename('fullpath'));
        addpath(fullfile(here, 'shims'));
        addpath(genpath(fullfile(here, 'msmv_code')));   % upstream mSMV functions + MEDI SMV helpers
        addpath(fullfile(here, 'nifti'));
    end

    %% ---- inputs ----------------------------------------------------------------------------------
    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0  = p.B0;                       % main field strength (T)
    vox = p.voxel_size(:)';           % mm
    gyro = 42.5774;                   % MHz/T (proton), CF = gyro*B0 in MHz

    tf_nii = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    totalfield = double(tf_nii.img);  % ppm
    mask = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;
    matrix_size = size(totalfield);

    %% ---- parameters (overridable via /input/config.json or `qsm-ci run --set NAME=VALUE`) --------
    cfg = struct();
    cfgPath = fullfile(inp, 'config.json');
    if exist(cfgPath, 'file') == 2
        cfg = jsondecode(fileread(cfgPath));
    end
    radius       = getparam(cfg, 'radius',       5);      % SMV prefilter kernel radius (mm), paper default
    maxk         = getparam(cfg, 'maxk',         5);      % max residual-removal iterations, paper default
    simulated_TE = getparam(cfg, 'simulated_TE', 0.008);  % TE (s) for the ppm<->rad conversion / threshold scale

    %% ---- ppm -> radians --------------------------------------------------------------------------
    % CF = gyro*B0 (MHz). rad = ppm * 1e-6 * 2*pi*CF*1e6 * TE = ppm * 2*pi*gyro*B0*TE .
    ppm2rad = 2*pi * gyro * B0 * simulated_TE;    % 1e6 (Hz/MHz) and 1e-6 (ppm) cancel
    RDF = totalfield * ppm2rad;                    % radians

    %% ---- mSMV (SMV primary removal + boundary shadow correction; prefilter=1) --------------------
    % Upstream signature: msmv(RDF, Mask, R2s, voxel_size, radius, maxk, vessel_radius, B0_mag, prefilter)
    % R2s all-zero -> vessel step skipped (see header). prefilter omitted -> defaults to 1 (SMV primary
    % removal happens inside msmv). B0_mag = B0 sets the radian shadow-threshold cap (0.01*B0/3).
    R2s = zeros(matrix_size);
    vessel_radius = 8 * max(vox(:));
    RDF_filt = msmv(RDF, double(mask), R2s, vox, radius, maxk, vessel_radius, B0);

    %% ---- radians -> ppm --------------------------------------------------------------------------
    localfield = (RDF_filt / ppm2rad) .* mask;     % ppm, restricted to the mask

    %% ---- write output ----------------------------------------------------------------------------
    tf_nii.img = single(localfield);
    tf_nii.hdr.dime.datatype = 16;  tf_nii.hdr.dime.bitpix = 32;
    write_niigz(tf_nii, fullfile(out, 'localfield.nii.gz'));
end

function v = getparam(cfg, name, default)
    if isstruct(cfg) && isfield(cfg, name) && ~isempty(cfg.(name))
        v = cfg.(name);
        if ischar(v) || isstring(v), v = str2double(v); end
    else
        v = default;
    end
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
