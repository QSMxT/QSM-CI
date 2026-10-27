function B = imerode(A, se)
% Binary/greyscale erosion shim (no Image Processing Toolbox). For binary uses the
% dilation duality erode(A) = ~dilate(~A) (matches IPT's "outside = foreground" border rule
% for symmetric structuring elements). The grey path pads with +Inf before shifting, IPT's
% border rule, so nothing wraps around the FOV (fidelity/REPORT.md).
    if islogical(A)
        B = ~imdilate(~A, se);
    else
        nh = local_nhood(se);
        off = nhood_offsets(nh);
        r = max(abs(off), [], 1);
        P = pad_const(A, r, Inf);
        B = inf(size(P), 'like', P);
        for k = 1:size(off,1)
            B = min(B, circshift(P, off(k,:)));
        end
        B = B(r(1)+1:end-r(1), r(2)+1:end-r(2), r(3)+1:end-r(3));
    end
end

function P = pad_const(A, r, v)
    sz = size(A); sz(end+1:3) = 1;
    P = repmat(cast(v, 'like', A), sz + 2 * r);
    P(r(1)+1:r(1)+sz(1), r(2)+1:r(2)+sz(2), r(3)+1:r(3)+sz(3)) = A;
end

function nh = local_nhood(se)
    if isstruct(se) && isfield(se, 'nhood'); nh = se.nhood; else; nh = logical(se); end
end

function off = nhood_offsets(nh)
    sz = size(nh); sz(end+1:3) = 1;
    c = (sz + 1) / 2;
    idx = find(nh); idx = idx(:); [i,j,k] = ind2sub(sz, idx);
    off = round([i,j,k] - c);
end
