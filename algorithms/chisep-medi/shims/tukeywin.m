function w = tukeywin(L, r)
% Drop-in for tukeywin (Signal Processing Toolbox): tapered-cosine window, taper ratio r.
    if nargin < 2 || isempty(r), r = 0.5; end
    if r <= 0, w = ones(L,1); return; end
    if r >= 1, r = 1; end
    t = ((0:L-1)')/(L-1);
    w = ones(L,1);
    lo = t < r/2;               w(lo) = 0.5*(1 + cos(pi*(2*t(lo)/r - 1)));
    hi = t >= (1 - r/2);        w(hi) = 0.5*(1 + cos(pi*(2*t(hi)/r - 2/r + 1)));
end
