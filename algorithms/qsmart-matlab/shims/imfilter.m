function B = imfilter(A, H, varargin)
% Minimal imfilter shim (no Image Processing Toolbox) for the forms the bundled Frangi
% filter's imgaussian.m uses: imfilter(I, H, 'same', 'replicate') with odd 1-D kernels
% oriented along one dimension. Implements IPT's default CORRELATION with replicate
% padding and 'same' output size ('same' + 'replicate' are accepted and assumed).
    nd = max(ndims(A), ndims(H));
    szH = size(H); szH(end+1:nd) = 1;
    pre = floor((szH - 1) / 2); post = szH - 1 - pre;
    P = A;
    for d = 1:nd
        if pre(d) == 0 && post(d) == 0, continue; end
        n = size(P, d);
        idx = [ones(1, pre(d)), 1:n, n * ones(1, post(d))];   % replicate
        subs = repmat({':'}, 1, nd);
        subs{d} = idx;
        P = P(subs{:});
    end
    Hf = H;
    for d = 1:ndims(H), Hf = flip(Hf, d); end                 % correlation via convn
    B = convn(P, Hf, 'valid');
end
