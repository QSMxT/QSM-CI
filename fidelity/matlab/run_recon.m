function run_recon(inp, outdir, deps, algo, spec, whichlist)
% Run an algorithm's recon.m in licensed MATLAB with the real toolboxes, writing its intermediates.
%   inp       contract inputs
%   outdir    receives the outputs and intermediates/
%   deps      the dependencies as the algorithm's fid_assemble lays them out (no shims)
%   algo      the algorithm folder (recon.m and its top-level helpers)
%   spec      FID_MATLAB_PATH (see fidelity_paths)
%   whichlist FID_WHICH: functions whose resolution is recorded in resolution.txt
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    fidelity_paths(deps, spec);
    addpath(algo);
    rehash;
    names = strsplit(strtrim(whichlist));
    fid = fopen(fullfile(outdir, 'resolution.txt'), 'w');
    for k = 1:numel(names)
        if ~isempty(names{k}), fprintf(fid, '%-28s %s\n', names{k}, which(names{k})); end
    end
    fclose(fid);
    type(fullfile(outdir, 'resolution.txt'));
    fidelity_env(fullfile(outdir, 'env.json'));
    setenv('QSMCI_INTERMEDIATES', fullfile(outdir, 'intermediates'));
    t = tic;
    recon(inp, outdir);
    fprintf('recon took %.0f s\n', toc(t));
end
