function BW = imbinarize(I, varargin)
% imbinarize shim (no Image Processing Toolbox).
%
% mSMV only uses the numeric-threshold form  imbinarize(I, t)  where `t` is an absolute scalar in
% [0,1] and the result is I > t applied to I WITHOUT rescaling (IPT's documented behaviour for a
% numeric scalar threshold: "BW = imbinarize(I,T) ... T ... in the range [0, 1]" and pixels with
% value > T become foreground). We also handle 'global' (Otsu) defensively.
    I = double(I);
    if nargin >= 2 && (isnumeric(varargin{1}) && isscalar(varargin{1}))
        t = varargin{1};
        BW = I > t;
    elseif nargin >= 2 && (ischar(varargin{1}) || isstring(varargin{1})) && ...
            strcmpi(varargin{1}, 'global')
        BW = I > otsu_threshold(I);
    else
        % Default (Otsu global), matching imbinarize(I) with no extra args.
        BW = I > otsu_threshold(I);
    end
    BW = logical(BW);
end

function level = otsu_threshold(I)
% Otsu global threshold on I rescaled to [0,1] (matches graythresh/imbinarize default scaling).
    v = I(:);
    v = v(isfinite(v));
    lo = min(v); hi = max(v);
    if hi <= lo
        level = lo;
        return;
    end
    x = (v - lo) / (hi - lo);
    [counts, edges] = histcounts(x, 256);
    binc = (edges(1:end-1) + edges(2:end)) / 2;
    p = counts / sum(counts);
    omega = cumsum(p);
    mu = cumsum(p .* binc);
    muT = mu(end);
    denom = omega .* (1 - omega);
    denom(denom == 0) = eps;
    sigma_b2 = (muT * omega - mu).^2 ./ denom;
    [~, idx] = max(sigma_b2);
    level = lo + binc(idx) * (hi - lo);
end
