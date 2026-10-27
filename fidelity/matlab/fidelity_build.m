function fidelity_build(B, spec, whichlist, mcc_a)
% Compile B/recon.m against the licensed toolboxes, with the dependencies in B/deps on the path in
% the FID_MATLAB_PATH order (as the licensed runs use them). Writes B/out/recon and mcc's reports,
% and prints what each function in WHICHLIST resolves to and which products the code needs.
%   mcc_a  cell array of extra mcc arguments, e.g. {'-a','deps/sti'} (pcode must be force-bundled)
    cd(B);
    fprintf('VERSION %s\n', version);
    assert(license('test', 'Compiler') == 1, 'no MATLAB Compiler license');
    fidelity_paths(fullfile(B, 'deps'), spec);
    rehash;
    names = strsplit(strtrim(whichlist));
    for k = 1:numel(names)
        if ~isempty(names{k}), fprintf('WHICH %s %s\n', names{k}, which(names{k})); end
    end
    [f, p] = matlab.codetools.requiredFilesAndProducts('recon.m');
    for k = 1:numel(p), fprintf('PRODUCT %s %s %d\n', p(k).Name, p(k).Version, p(k).ProductNumber); end
    t = f(startsWith(f, fullfile(matlabroot, 'toolbox')));
    if ~isempty(t), fprintf('TOOLBOXFILE %s\n', t{:}); end
    if ~exist('out', 'dir'), mkdir('out'); end
    mcc('-m', 'recon.m', mcc_a{:}, '-o', 'recon', '-d', 'out', '-v');
end
