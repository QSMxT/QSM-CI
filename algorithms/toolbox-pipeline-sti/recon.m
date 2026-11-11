function recon(inp, out)
% QSM-CI `pipeline` span in MATLAB: STI Suite 3.0's QSM_GUI iLSQR pipeline, from the echoes to χ, as
% the reference for QSMxT's `sti-suite-ilsqr` pipeline (QSMxT/QSM-CI#421). The STI pipeline is the
% GUI's iLSQR path (decisions 15(2), 27): its "Thresholding", "V-SHARP" and "iLSQR" buttons.
% Reads <inp>/phase.nii.gz (rad, echoes on dim 4), magnitude.nii.gz and params.json; writes
% <out>/chimap.nii.gz (ppm).
%
% The chain was read off by driving QSM_GUI headless in licensed MATLAB R2023b with every call
% logged (QSM-CI#421 STI probe, 2026-11-11; s005001 Prisma). The GUI and its glue (mythresh) are
% P-code with figures, so the glue is written out here; every computation is STI Suite's own
% function or the MATLAB function the GUI calls:
%   level = thresh_tool's starting level on the middle slice of the last echo's magnitude, scaled to
%           256 (Support_Functions/thresh_tool.m l. 15-36, 84-89, 143: graythresh). The GUI keeps
%           it unless the user drags the line.
%   mask  = Mag/max(slice)*256 > level -> largest bwlabeln component (regionprops 'Area') ->
%           regionprops 'FilledImage' in its 'BoundingBox'                       (mythresh)
%   phi   = sum over echoes of MRPhaseUnwrap(phase, 'voxelsize', vox)  (4-D, single, as loaded)
%   [TissuePhase, mask2] = V_SHARP(phi, mask, 'voxelsize', vox, 'smvsize', 12)
%   mask3 = PolishMask(mask2)                                   (STI Suite GUI_Functions_P)
%   chi   = QSM_iLSQR(TissuePhase .* mask3, mask3, 'params', struct(niter 40, padsize 12,
%           tol_step1 0.01, tol_step2 0.001, Kthreshold 0.1, TE = ΣTE ms, B0, H, voxelsize))
% The GUI keeps chi as QSM_iLSQR returns it (no referencing). B0 and H are what the user types in
% the GUI; here params.json's B0 and B0_dir. The GUI holds the mask with only the slices up to its
% bounding box's last (126 of 128 on the probe scan) and hands V_SHARP that; here the mask keeps the
% volume's size (the slices after are outside it either way). README.md: Fidelity.
%
% Bundled: Jimmy Shen NIfTI toolbox, STI Suite 3.0 Core_Functions_P and GUI_Functions_P/PolishMask
% (P-code), and the Image Processing Toolbox functions (BUILD.md). OS gunzip/gzip (no JVM).
%
% Intermediates (QSMCI_INTERMEDIATES, a directory or 1 for <out>/intermediates), under the names
% QSMxT's candidate writes (CONTRACT.md "Intermediates"): mask (the thresholding mask), mask_bfr
% (PolishMask's), totalfield (ppm: Σφ/(2π·γ·B0·ΣTE)), localfield (ppm, V_SHARP's inside PolishMask's
% mask); also the level.

%#function imclose imdilate imerode padarray strel graythresh bwlabeln regionprops imfill
%#function PolishMask MRPhaseUnwrap V_SHARP QSM_iLSQR

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    H   = p.B0_dir(:)'; H = H / norm(H);
    vox = double(p.voxel_size(:)');
    B0  = double(p.B0);
    TE  = double(p.TE(:)');

    nph   = read_niigz(fullfile(inp, 'phase.nii.gz'));
    phase = single(nph.img);                                   % the GUI loads single
    Mag   = single(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    nte = size(phase, 4);
    if nte ~= numel(TE) || size(Mag, 4) ~= nte
        error('recon:te', 'phase has %d echoes, magnitude %d, params.json %d echo times', ...
              nte, size(Mag, 4), numel(TE));
    end
    Mag = Mag(:, :, :, end);                                    % the last volume loaded

    % --- Thresholding (mythresh + thresh_tool) ---
    z0  = round(size(Mag, 3) / 2);
    S   = Mag(:, :, z0);
    S   = S / max(S(:)) * 256;
    level = thresh_tool_level(S);
    bw  = Mag / max(max(Mag(:, :, z0))) * 256 > level;
    L   = bwlabeln(bw);
    a   = regionprops(L, 'Area');
    [~, k] = max([a.Area]);
    big = L == k;
    r   = regionprops(uint8(big), 'FilledImage', 'BoundingBox');
    bb  = r.BoundingBox;                                        % [x y z w h d], half-voxel edges
    lo  = ceil(bb([2 1 3]));  hi = lo + bb([5 4 6]) - 1;        % rows (dim 1) are BoundingBox's y
    Mask = zeros(size(Mag));
    Mask(lo(1):hi(1), lo(2):hi(2), lo(3):hi(3)) = r.FilledImage;

    % --- V-SHARP button ---
    phi = sum(MRPhaseUnwrap(phase, 'voxelsize', vox), 4);
    [TissuePhase, mask2] = V_SHARP(phi, Mask, 'voxelsize', vox, 'smvsize', 12);
    mask3 = PolishMask(mask2);

    % --- iLSQR button ---
    params = struct('B0', B0, 'H', H, 'Kthreshold', 0.1, 'TE', sum(TE) * 1000, 'niter', 40, ...
                    'padsize', [12 12 12], 'tol_step1', 0.01, 'tol_step2', 0.001, 'voxelsize', vox);
    chi = QSM_iLSQR(TissuePhase .* double(mask3), mask3, 'params', params);

    tmpl = nph;
    to_ppm = 1e6 / (2*pi * 42.576e6 * B0 * sum(TE));
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(tmpl, double(Mask), fullfile(idir, 'mask.nii.gz'));
        write_intermediate(tmpl, double(mask3), fullfile(idir, 'mask_bfr.nii.gz'));
        write_intermediate(tmpl, double(phi) * to_ppm, fullfile(idir, 'totalfield.nii.gz'));
        write_intermediate(tmpl, TissuePhase .* double(mask3) * to_ppm, fullfile(idir, 'localfield.nii.gz'));
        write_meta(idir, struct('level', double(level), 'middle_slice', z0));
    end

    tmpl.img = single(chi);
    tmpl.hdr.dime.datatype = 16;  tmpl.hdr.dime.bitpix = 32;
    tmpl.hdr.dime.dim(1) = 3;  tmpl.hdr.dime.dim(5) = 1;
    tmpl.hdr.dime.scl_slope = 1;  tmpl.hdr.dime.scl_inter = 0;
    write_niigz(tmpl, fullfile(out, 'chimap.nii.gz'));
end

function level = thresh_tool_level(image)
% STI Suite Support_Functions/thresh_tool.m's starting level, the lines that compute it (15-36,
% 84-89, 143), without its figure. `image` is single, as the GUI hands it over.
    max_colors = max(image(:));
    im = round(image / max_colors * 512);
    color_range = double([min(im(:)) max(im(:))]);              % limits(im)
    lo = color_range(1);  hi = color_range(2);
    norm_im = (double(im) - lo) / (hi - lo);
    norm_level = graythresh(norm_im);
    my_level = norm_level * (hi - lo) + lo;
    level = my_level / 512 * max_colors;
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

function tb = toolbox_functions()
    tb = {'graythresh', 'bwlabeln', 'regionprops', 'imfill', 'imclose', 'imdilate', 'imerode', ...
          'padarray', 'strel', 'PolishMask', 'MRPhaseUnwrap', 'V_SHARP', 'QSM_iLSQR'};
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
% intermediates.json: M plus the MATLAB version, the thread count, and where each function in the
% %#function pragma resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
