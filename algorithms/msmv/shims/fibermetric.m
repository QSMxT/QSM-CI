function V = fibermetric(I, varargin)
% fibermetric shim (no Image Processing Toolbox).
%
% mSMV uses fibermetric (Frangi vesselness) ONLY to build a vessel-protection mask from an R2* map,
% so that bright tubular vessels are not filtered as background field. The QSM-CI `bfr` stage does
% not provide an R2* map, so recon.m passes an all-zero R2*; the upstream README states this vessel
% step is "skipped" when R2* is missing.
%
% We honour that by returning an all-zero vesselness response: downstream mSMV does
% imbinarize(fibermetric(...),0), i.e. (V > 0), which is then empty (no voxels protected as vessels).
% A structured input (nonzero R2*) never reaches this shim from the bfr stage; if it ever did, the
% empty response would simply mean "no vessel protection" — a safe, conservative default (mSMV would
% then be free to filter everywhere, exactly as if R2* were unavailable).
    V = zeros(size(I));
end
