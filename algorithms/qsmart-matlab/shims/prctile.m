function y = prctile(x, p)
% Percentile shim (no Statistics and Machine Learning Toolbox), matching MATLAB's
% definition (linear interpolation between the midpoint positions (0.5:n-0.5)/n*100).
% Only referenced by QSMART's optional adaptive-threshold branches (off by default);
% bundled so mcc resolves the symbol and the branch works if ever enabled.
    x = sort(double(x(~isnan(x))));
    x = x(:);
    n = numel(x);
    if n == 0, y = nan(size(p)); return; end
    if n == 1, y = repmat(x, size(p)); return; end
    q = (0.5:n - 0.5) / n * 100;
    y = interp1([0, q, 100], [x(1); x; x(end)], p, 'linear');
end
