function level = graythresh(I)
% Otsu global-threshold shim (no Image Processing Toolbox), following IPT conventions:
% double input is treated as an intensity image on [0,1] (values clipped), the histogram
% has 256 bins, and the returned level is a normalized value in [0,1].
% QSMART thresholds the Frangi vesselness map (range [0,1]) with this.
    v = double(I(:));
    v = v(isfinite(v));
    if isempty(v), level = 0; return; end
    v(v < 0) = 0; v(v > 1) = 1;
    counts = histcounts(v, linspace(0, 1, 257));
    p = counts / max(1, sum(counts));
    binc = ((0:255) + 0.5) / 256;
    omega = cumsum(p);
    mu = cumsum(p .* binc);
    muT = mu(end);
    denom = omega .* (1 - omega);
    denom(denom <= 0) = eps;
    sigma_b2 = (muT * omega - mu).^2 ./ denom;
    [~, idx] = max(sigma_b2);
    level = (idx - 1) / 255;
end
