function BW2 = imfill(BW, varargin)
% imfill(BW, conn, 'holes') — fill holes in a binary image, without the
% Image Processing Toolbox. A hole is background not reachable from the
% array border, so this floods the complement inward from the border and
% keeps whatever the flood never reached.
%
% Only the 'holes' form is implemented; that is all the UK Biobank pipeline uses.
    conn = [];
    holes = false;
    for k = 1:numel(varargin)
        v = varargin{k};
        if ischar(v) || (isstring(v) && isscalar(v))
            if strcmpi(char(v), 'holes'), holes = true; else
                error('imfill shim: only the ''holes'' form is supported'); end
        else
            conn = v;
        end
    end
    if ~holes, error('imfill shim: only the ''holes'' form is supported'); end
    BW = logical(BW);
    sz = size(BW);
    if numel(sz) < 3, sz(3) = 1; end
    if isempty(conn), conn = (sz(3) > 1) * 26 + (sz(3) == 1) * 8; end
    % Background connectivity is the complement of the foreground's; IPT uses the
    % same value for the flood here and the UKB calls pass 26 on 3-D volumes.
    bg = ~BW;
    % Seed the flood from every background voxel on the array border.
    seed = false(sz);
    seed([1 sz(1)], :, :) = true;
    seed(:, [1 sz(2)], :) = true;
    seed(:, :, [1 sz(3)]) = true;
    seed = seed & bg;
    [L, n] = qsmci_label(bg, conn);
    BW2 = BW;
    if n == 0, return; end
    outside = unique(L(seed));
    outside(outside == 0) = [];
    % Background components never touched by the border are holes: fill them.
    BW2(bg & ~ismember(L, outside)) = true;
end
