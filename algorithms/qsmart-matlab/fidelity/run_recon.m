function run_recon(mode, inp, outdir, deps, algo)
% Run qsmart-matlab's recon.m in licensed MATLAB, writing the intermediates.
%   mode  'real'        the licensed toolboxes, as the container's build compiles them
%   inp     contract inputs (phase, magnitude, mask, params.json)
%   outdir  receives chimap.nii.gz and intermediates/
%   deps    assemble_deps.sh output (eig3volume mex built)
%   algo    algorithms/qsmart-matlab (recon.m, vasculature_mask_qsmci.m)
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    fdir = fileparts(mfilename('fullpath'));
    for d = {'sti', 'curvatures', 'frangi', 'qsmart', 'nifti'}
        addpath(fullfile(deps, d{1}));      % ends up nifti, qsmart, frangi, curvatures, sti
    end
    addpath(algo);
    addpath(fdir);
    if ~strcmp(mode, 'real'), error('unknown mode %s', mode); end
    rehash;

    % Record what each toolbox name resolves to.
    names = {'graythresh', 'imbothat', 'imclose', 'imdilate', 'imerode', 'imfilter', ...
             'imgaussfilt3', 'imopen', 'padarray', 'prctile', 'strel', 'vasculature_mask_qsmci', ...
             'QSM_iLSQR', 'FrangiFilter3D', 'eig3volume', 'imgaussian', 'N4BiasFieldCorrection'};
    fid = fopen(fullfile(outdir, 'resolution.txt'), 'w');
    for k = 1:numel(names), fprintf(fid, '%-24s %s\n', names{k}, which(names{k})); end
    [~, n4] = system('command -v N4BiasFieldCorrection'); fprintf(fid, 'N4 binary: %s', n4);
    fclose(fid);
    type(fullfile(outdir, 'resolution.txt'));
    fidelity_env(fullfile(outdir, 'env.json'));

    setenv('QSMCI_INTERMEDIATES', fullfile(outdir, 'intermediates'));
    t = tic;
    recon(inp, outdir);
    fprintf('recon (%s) took %.0f s\n', mode, toc(t));
end
