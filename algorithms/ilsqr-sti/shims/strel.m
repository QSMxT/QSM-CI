function se = strel(shape, varargin)
% Minimal structuring-element replacement (no Image Processing Toolbox), covering the
% shapes QSM toolboxes use. Returns a struct with a logical neighbourhood `.nhood` that the
% bundled imdilate/imerode shims consume. Supports strel(nhoodMatrix), strel('sphere',r),
% strel('disk',r[,0]), strel('cube',w), strel('square',w), strel('line',len,deg is approximated).
    if nargin == 1 && (islogical(shape) || isnumeric(shape))
        se.nhood = logical(shape); return
    end
    switch lower(shape)
        case 'sphere'
            r = varargin{1}; [x,y,z] = ndgrid(-r:r, -r:r, -r:r);
            se.nhood = (x.^2 + y.^2 + z.^2) <= r^2;
        case {'disk'}
            r = varargin{1}; [x,y] = ndgrid(-r:r, -r:r);
            se.nhood = (x.^2 + y.^2) <= r^2;
        case {'cube'}
            w = varargin{1}; se.nhood = true(w, w, w);
        case {'square'}
            w = varargin{1}; se.nhood = true(w, w);
        case {'line'}
            len = round(varargin{1}); se.nhood = true(1, max(1, len));
        otherwise
            r = 1; if ~isempty(varargin) && isnumeric(varargin{1}), r = varargin{1}; end
            [x,y,z] = ndgrid(-r:r, -r:r, -r:r);
            se.nhood = (abs(x)+abs(y)+abs(z)) <= r;   % diamond fallback
    end
    se.nhood = logical(se.nhood);
end
