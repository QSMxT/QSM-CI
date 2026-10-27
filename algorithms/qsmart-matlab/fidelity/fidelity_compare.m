function c = fidelity_compare(got, ref)
% Compare a shim result GOT with the toolbox result REF.
%   identical  isequaln (same size, same values; class is reported separately)
%   maxabs     max |got - ref| (Inf where only one side is Inf/NaN)
%   maxrel     maxabs / max |ref| over finite ref values
%   ndiff      number of elements that differ
    if isa(got, 'strel'), got = got.Neighborhood; end
    if isa(ref, 'strel'), ref = ref.Neighborhood; end
    if isstruct(got) && isfield(got, 'nhood'), got = got.nhood; end
    c = struct('class_got', class(got), 'class_ref', class(ref), ...
               'size_got', mat2str(size(got)), 'size_ref', mat2str(size(ref)), ...
               'identical', false, 'maxabs', Inf, 'maxrel', Inf, 'ndiff', NaN, 'numel', numel(ref));
    if ~isequal(size(got), size(ref)), return; end
    c.identical = isequaln(double(got), double(ref));
    g = double(got(:)); r = double(ref(:));
    same = (g == r) | (isnan(g) & isnan(r));
    d = abs(g - r); d(same) = 0; d(isnan(d)) = Inf;
    c.ndiff = nnz(d);
    c.maxabs = max([d; 0]);
    s = max(abs(r(isfinite(r))));
    if isempty(s) || s == 0, s = 1; end
    c.maxrel = c.maxabs / s;
end
