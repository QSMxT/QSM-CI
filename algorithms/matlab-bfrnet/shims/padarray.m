function B = padarray(A, padsize, varargin)
% Minimal zero-padding replacement for the Image Processing Toolbox padarray,
% so recon.m compiles/runs on the MATLAB Runtime (no IPT). Supports the forms used here:
%   padarray(A, p)              padarray(A, p, dir)
%   padarray(A, p, val, dir)    (val numeric; dir 'pre'|'post'|'both')
% recon.m uses padarray(tfs, pad, 0, 'post') to reach a multiple of 8.
% Only constant-value padding is implemented ('circular'/'replicate'/'symmetric'
% are not used here).
    padval = 0; direction = 'both';
    for k = 1:numel(varargin)
        v = varargin{k};
        if ischar(v) || (isstring(v) && isscalar(v))
            direction = char(v);
        else
            padval = v;
        end
    end
    padsize = double(padsize(:)');
    nd = max(ndims(A), numel(padsize));
    padsize(end+1:nd) = 0;
    sz = size(A); sz(end+1:nd) = 1;
    switch lower(direction)
        case 'pre',  pre = padsize;         post = zeros(1, nd);
        case 'post', pre = zeros(1, nd);    post = padsize;
        otherwise,   pre = padsize;         post = padsize;   % 'both'
    end
    B = repmat(cast(padval, 'like', A), sz + pre + post);
    idx = arrayfun(@(d) (pre(d) + 1):(pre(d) + sz(d)), 1:nd, 'UniformOutput', false);
    B(idx{:}) = A;
end
