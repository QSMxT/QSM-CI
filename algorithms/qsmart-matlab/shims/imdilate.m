function B = imdilate(A, se)
% Binary/greyscale dilation shim (no Image Processing Toolbox). Uses a flat structuring
% element (max over the neighbourhood via convn for binary, or ordfilt-style for grey).
% Like IPT, pixels beyond the border count as -Inf (grey) / false (binary): the grey path pads
% before shifting, so nothing wraps around the FOV (fidelity/REPORT.md).
    nh = local_nhood(se);
    if islogical(A)
        B = convn(double(A), double(nh), 'same') > 0;
    else
        B = grey_morph(A, nh, @max);
    end
end

function nh = local_nhood(se)
    if isstruct(se) && isfield(se, 'nhood'); nh = se.nhood; else; nh = logical(se); end
end

function B = grey_morph(A, nh, redfun)
    off = nhood_offsets(nh);
    r = max(abs(off), [], 1);
    P = pad_const(A, r, -Inf);
    B = -inf(size(P), 'like', P);
    for k = 1:size(off,1)
        B = redfun(B, circshift(P, off(k,:)));
    end
    B = B(r(1)+1:end-r(1), r(2)+1:end-r(2), r(3)+1:end-r(3));
end

function P = pad_const(A, r, v)
    sz = size(A); sz(end+1:3) = 1;
    P = repmat(cast(v, 'like', A), sz + 2 * r);
    P(r(1)+1:r(1)+sz(1), r(2)+1:r(2)+sz(2), r(3)+1:r(3)+sz(3)) = A;
end

function off = nhood_offsets(nh)
    sz = size(nh); sz(end+1:3) = 1;
    c = (sz + 1) / 2;
    idx = find(nh); idx = idx(:); [i,j,k] = ind2sub(sz, idx);
    off = round([i,j,k] - c);
end
