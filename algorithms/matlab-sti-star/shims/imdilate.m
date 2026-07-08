function B = imdilate(A, se)
% Binary/greyscale dilation shim (no Image Processing Toolbox). Uses a flat structuring
% element (max over the neighbourhood via convn for binary, or ordfilt-style for grey).
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
    B = -inf(size(A));
    if isequal(redfun, @min), B = inf(size(A)); end
    for k = 1:size(off,1)
        B = redfun(B, circshift(A, off(k,:)));
    end
end

function off = nhood_offsets(nh)
    sz = size(nh); sz(end+1:3) = 1;
    c = (sz + 1) / 2;
    idx = find(nh); idx = idx(:); [i,j,k] = ind2sub(sz, idx);
    off = round([i,j,k] - c);
end
