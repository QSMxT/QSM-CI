function [L, n] = qsmci_label(BW, conn)
% Connected-component labelling for 2-D or 3-D logical arrays, without the
% Image Processing Toolbox. `conn` is 4 or 8 (2-D) or 6, 18 or 26 (3-D).
%
% Builds the neighbour edge list with vectorised array shifts and hands it to
% base MATLAB's graph/conncomp. A per-voxel flood fill in interpreted code is
% orders of magnitude slower: on one 164x205 brain slice it cost ~15 s, which
% the UK Biobank mask cleanup would multiply by 205 slices and four passes.
    BW = logical(BW);
    sz = size(BW);
    if numel(sz) < 3, sz(3) = 1; end
    L = zeros(sz);
    n = 0;
    vox = find(BW);
    if isempty(vox), return; end

    [di, dj, dk] = ndgrid(-1:1, -1:1, -1:1);
    off = [di(:) dj(:) dk(:)];
    off(all(off == 0, 2), :) = [];
    d1 = sum(abs(off), 2);
    switch conn
        case 4,  keep = (d1 == 1) & (off(:,3) == 0);
        case 8,  keep = (off(:,3) == 0);
        case 6,  keep = (d1 == 1);
        case 18, keep = (d1 <= 2);
        case 26, keep = true(size(d1));
        otherwise, error('qsmci_label: unsupported connectivity %d', conn);
    end
    off = off(keep, :);
    % The graph is undirected, so only half the offsets are needed: keep those
    % whose first non-zero component is positive.
    fwd = false(size(off,1),1);
    for t = 1:size(off,1)
        v = off(t,:); v = v(find(v ~= 0, 1));
        fwd(t) = v > 0;
    end
    off = off(fwd, :);

    idx = reshape(1:numel(BW), sz);
    compact = zeros(numel(BW), 1);
    compact(vox) = 1:numel(vox);

    src = cell(size(off,1),1); dst = cell(size(off,1),1);
    for t = 1:size(off,1)
        o = off(t,:);
        a = max(1, 1-o(1)) : min(sz(1), sz(1)-o(1));
        b = max(1, 1-o(2)) : min(sz(2), sz(2)-o(2));
        c = max(1, 1-o(3)) : min(sz(3), sz(3)-o(3));
        if isempty(a) || isempty(b) || isempty(c), continue; end
        both = BW(a,b,c) & BW(a+o(1), b+o(2), c+o(3));
        if ~any(both(:)), continue; end
        ia = idx(a,b,c); ib = idx(a+o(1), b+o(2), c+o(3));
        src{t} = compact(ia(both)); dst{t} = compact(ib(both));
    end
    src = vertcat(src{:}); dst = vertcat(dst{:});

    if isempty(src)
        L(vox) = 1:numel(vox); n = numel(vox); return;     % all isolated
    end
    G = graph(src, dst, [], numel(vox));
    c = conncomp(G);
    L(vox) = c;
    n = max(c);
end
