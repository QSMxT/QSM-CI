function B = imgaussfilt3(A, sigma, varargin)
% 3-D Gaussian smoothing shim (no Image Processing Toolbox), matching the IPT behaviour
% QSMART relies on: separable Gaussian, per-axis sigma (scalar or 3-vector), replicate
% ("border extension") padding, and the 'FilterSize' name-value pair (scalar or 3-vector;
% default 2*ceil(2*sigma)+1 per axis). QSMART calls it as imgaussfilt3(I,[s 2s 2s]),
% imgaussfilt3(I,s) and imgaussfilt3(I,s,'filterSize',k).
    if nargin < 2 || isempty(sigma), sigma = 0.5; end
    sigma = double(sigma(:)');
    if isscalar(sigma), sigma = [sigma sigma sigma]; end
    fs = 2 * ceil(2 * sigma) + 1;
    for k = 1:2:numel(varargin)
        if strcmpi(char(varargin{k}), 'FilterSize')
            v = double(varargin{k+1}); v = v(:)';
            if isscalar(v), v = [v v v]; end
            fs = v;
        end
    end
    fs = fs + (mod(fs, 2) == 0);          % force odd sizes (IPT requires odd)
    B = double(A);
    for d = 1:3
        r = (fs(d) - 1) / 2;
        if r <= 0 || sigma(d) <= 0, continue; end
        x = -r:r;
        h = exp(-(x.^2) / (2 * sigma(d)^2));
        h = h / sum(h);
        B = filt1_replicate(B, h, d, r);
    end
end

function B = filt1_replicate(A, h, d, r)
% Replicate-pad A along dim d by r, then 'valid' convolution with the 1-D kernel
% (kernel is symmetric, so convolution == correlation).
    n = size(A, d);
    idx = [ones(1, r), 1:n, n * ones(1, r)];
    subs = repmat({':'}, 1, max(3, ndims(A)));
    subs{d} = idx;
    P = A(subs{:});
    shape = ones(1, max(3, d)); shape(d) = numel(h);
    K = reshape(h, shape);
    B = convn(P, K, 'valid');
end
