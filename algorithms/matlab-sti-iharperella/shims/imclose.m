function B = imclose(A, se)
% Morphological closing shim: dilate then erode (no Image Processing Toolbox).
    B = imerode(imdilate(A, se), se);
end
