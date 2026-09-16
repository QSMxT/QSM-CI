function BW2 = imfill(BW, varargin)
% imfill(BW, conn, 'holes') — fill holes in a binary image, without the
% Image Processing Toolbox. A hole is background the array border cannot reach,
% so this floods the complement inward from the border and keeps what it never
% reaches.
%
% The flood is a geodesic dilation done with array shifts. A 3x3x3 all-ones
% structuring element is separable, so 26-connectivity costs three 1-D
% dilations per iteration rather than 26 shifts, and no labelling is needed.
%
% Only the 'holes' form is implemented; that is all the UK Biobank pipeline uses.
    conn = []; holes = false;
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
    if isempty(conn), conn = 26 * (sz(3) > 1) + 8 * (sz(3) == 1); end
    full_nbhd = ismember(conn, [8 26]);          % separable cube vs. face-only

    bg = ~BW;
    R = false(sz);                               % reached-from-border set
    R([1 sz(1)], :, :) = true;
    R(:, [1 sz(2)], :) = true;
    R(:, :, [1 sz(3)]) = true;
    R = R & bg;

    while true
        prev = R;
        R = dilate_once(R, full_nbhd) & bg;
        if isequal(R, prev), break; end
    end
    BW2 = BW | (bg & ~R);
end

function D = dilate_once(R, full_nbhd)
% One step of binary dilation: face neighbours always, plus the separable
% diagonal reach when the full 3x3x3 neighbourhood is requested.
    D = R;
    for d = 1:3
        if size(R, d) < 2, continue; end
        D = D | shift_or(D, d);
        if ~full_nbhd
            % face-only: each axis contributes independently of the others,
            % so re-seed from R rather than the partially dilated D.
            D = D | shift_or(R, d);
        end
    end
end

function S = shift_or(A, d)
% A OR its one-voxel shifts along dimension d, in both directions.
    S = A;
    switch d
        case 1
            S(2:end,:,:)   = S(2:end,:,:)   | A(1:end-1,:,:);
            S(1:end-1,:,:) = S(1:end-1,:,:) | A(2:end,:,:);
        case 2
            S(:,2:end,:)   = S(:,2:end,:)   | A(:,1:end-1,:);
            S(:,1:end-1,:) = S(:,1:end-1,:) | A(:,2:end,:);
        case 3
            S(:,:,2:end)   = S(:,:,2:end)   | A(:,:,1:end-1);
            S(:,:,1:end-1) = S(:,:,1:end-1) | A(:,:,2:end);
    end
end
