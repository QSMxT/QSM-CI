function B = imerode(A, se)
% Binary/greyscale erosion shim (no Image Processing Toolbox). For binary uses the
% dilation duality erode(A) = ~dilate(~A) (matches IPT's "outside = foreground" border rule
% for symmetric structuring elements).
    if islogical(A)
        B = ~imdilate(~A, se);
    else
        nh = local_nhood(se);
        off = nhood_offsets(nh);
        B = inf(size(A));
        for k = 1:size(off,1)
            B = min(B, circshift(A, off(k,:)));
        end
    end
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
