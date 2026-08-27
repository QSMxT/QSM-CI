function B = imbothat(A, se)
% Bottom-hat (black top-hat) shim: closing minus the image (no Image Processing Toolbox).
% QSMART's vasculature_mask uses this on the (bias-corrected) mean-echo magnitude with a
% spherical structuring element to highlight dark tubular structures (veins).
    B = imclose(A, se) - A;
end
