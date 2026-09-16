function [L, n] = qsmci_label(BW, conn)
% Connected-component labelling for 2-D or 3-D logical arrays, without the
% Image Processing Toolbox. `conn` is 4 or 8 (2-D) or 6, 18 or 26 (3-D).
% Breadth-first flood fill over linear indices; adequate for the volumes here.
    BW = logical(BW);
    sz = size(BW);
    if numel(sz) < 3, sz(3) = 1; end
    L = zeros(sz);
    n = 0;

    % Neighbour offsets as (di,dj,dk) triples for the requested connectivity.
    [di, dj, dk] = ndgrid(-1:1, -1:1, -1:1);
    off = [di(:) dj(:) dk(:)];
    off(all(off == 0, 2), :) = [];                 % drop the centre
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

    idx = find(BW(:))';
    for seed = idx
        if L(seed) ~= 0, continue; end
        n = n + 1;
        queue = seed;
        L(seed) = n;
        while ~isempty(queue)
            cur = queue(end); queue(end) = [];
            [i, j, k] = ind2sub(sz, cur);
            for t = 1:size(off, 1)
                a = i + off(t,1); b = j + off(t,2); c = k + off(t,3);
                if a < 1 || b < 1 || c < 1 || a > sz(1) || b > sz(2) || c > sz(3), continue; end
                p = sub2ind(sz, a, b, c);
                if BW(p) && L(p) == 0
                    L(p) = n;
                    queue(end+1) = p; %#ok<AGROW>
                end
            end
        end
    end
end
