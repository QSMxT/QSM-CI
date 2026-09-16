function BW2 = bwareaopen(BW, P, conn)
% Remove connected components smaller than P pixels. Replacement for the
% Image Processing Toolbox bwareaopen; the UK Biobank pipeline calls it
% slice-by-slice on 2-D masks, where IPT's default connectivity is 8.
    if nargin < 3
        if ndims(BW) > 2 && size(BW, 3) > 1, conn = 26; else, conn = 8; end
    end
    BW = logical(BW);
    [L, n] = qsmci_label(BW, conn);
    BW2 = BW;
    if n == 0, return; end
    counts = accumarray(L(L > 0), 1, [n 1]);
    small = find(counts < P);
    if ~isempty(small)
        BW2(ismember(L, small)) = false;
    end
end
