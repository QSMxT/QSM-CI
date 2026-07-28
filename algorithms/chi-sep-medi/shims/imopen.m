function B = imopen(A, se)
% Morphological opening shim: erode then dilate (no Image Processing Toolbox).
    B = imdilate(imerode(A, se), se);
end
