function B = imclose(A, se)
% Morphological closing shim: dilate then erode (no Image Processing Toolbox). Like IPT, the
% image is first padded with background (false / -Inf) by the structuring element's radius and
% the result cropped back, so a mask that touches the FOV is not closed against the border
% (fidelity/REPORT.md).
    if isstruct(se) && isfield(se, 'nhood'); nh = se.nhood; else; nh = logical(se); end
    sz = size(nh); sz(end+1:3) = 1;
    r = floor(sz / 2);
    if islogical(A), v = false; else, v = -Inf; end
    s = size(A); s(end+1:3) = 1;
    P = repmat(cast(v, 'like', A), s + 2 * r);
    P(r(1)+1:r(1)+s(1), r(2)+1:r(2)+s(2), r(3)+1:r(3)+s(3)) = A;
    B = imerode(imdilate(P, se), se);
    B = B(r(1)+1:end-r(1), r(2)+1:end-r(2), r(3)+1:end-r(3));
end
