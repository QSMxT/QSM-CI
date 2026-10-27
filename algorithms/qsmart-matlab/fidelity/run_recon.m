function run_recon(mode, inp, outdir, deps, algo)
% Run qsmart-matlab's recon.m in licensed MATLAB, writing the intermediates.
%   mode  'real'        the licensed toolboxes (shims/ NOT on the path)
%         'shim'        shims/ first on the path, as in the mcc build (BUILD.md §3)
%         'trace'       like 'shim', with every shim call also checked against the toolbox
%                       (fidelity_trace_setup.m; log in <outdir>/trace)
%         'real-single' like 'real', with the vessel mask run in single precision as the
%                       authors' vasculature_mask.m does (N4's float32 output is not cast to
%                       double); informational, to size that deviation
%   inp     contract inputs (phase, magnitude, mask, params.json)
%   outdir  receives chimap.nii.gz and intermediates/
%   deps    assemble_deps.sh output (eig3volume mex built)
%   algo    algorithms/qsmart-matlab (recon.m, vasculature_mask_qsmci.m, shims/)
    global QSMCI_FIDELITY %#ok<GVMIS>
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    fdir = fileparts(mfilename('fullpath'));
    for d = {'sti', 'curvatures', 'frangi', 'qsmart', 'nifti'}
        addpath(fullfile(deps, d{1}));      % ends up nifti, qsmart, frangi, curvatures, sti
    end
    addpath(algo);
    addpath(fdir);
    switch mode
        case {'real', 'real-single'}
            % nothing: the toolbox functions resolve
        case 'shim'
            addpath(fullfile(algo, 'shims'));
        case 'trace'
            fidelity_trace_setup(fullfile(algo, 'shims'), fullfile(outdir, 'trace'));
        otherwise
            error('unknown mode %s', mode);
    end
    if strcmp(mode, 'real-single')
        tmp = tempname; mkdir(tmp);
        src = fileread(fullfile(algo, 'vasculature_mask_qsmci.m'));
        n = numel(strfind(src, 'AvgEcho_n4 = double(nii.img);'));
        assert(n == 1, 'real-single: expected one double() cast of the N4 output');
        src = strrep(src, 'AvgEcho_n4 = double(nii.img);', 'AvgEcho_n4 = nii.img;  % fidelity: original single precision');
        fid = fopen(fullfile(tmp, 'vasculature_mask_qsmci.m'), 'w'); fwrite(fid, src); fclose(fid);
        addpath(tmp);
    end
    rehash;

    % Record what each shimmed name resolves to in this mode.
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

    if strcmp(mode, 'trace')
        fclose(QSMCI_FIDELITY.fid);
        fprintf('trace: %d shim calls logged\n', QSMCI_FIDELITY.n);
    end
end
