function T = compare_runs(casedir, maskfile, deps, outmd)
% Container fidelity (QSMxT/QSM-CI#295, step 2): compare the runs of one case.
%   casedir/<run>/chimap.nii.gz and casedir/<run>/intermediates/*.nii.gz, runs:
%     container    the pinned image on Apptainer (with intermediates if the image has the
%                  QSMCI_INTERMEDIATES option, else the final chi only)
%     real, real2  licensed MATLAB with the real toolboxes, twice (run-to-run floor)
%     real-<tag>   real with another algorithm copy or setting (submit.sh FID_TAG), e.g. a
%                  different thread count
%   maskfile  the case's mask.nii.gz (NRMSE is taken inside it)
% Metrics: NRMSE % = 100 ||a - b|| / ||b|| inside the mask, b the reference run; max |a - b| over
% the volume; Dice for the masks (vessels = mask & ~vasc_only; R_0 rejects = mask & ~R_0), with
% each set's fraction of the brain mask.
    addpath(fullfile(deps, 'nifti'));
    mask = rd(maskfile) > 0.5;
    pairs = {'container', 'real',  'all';
             'real2',     'real',  'all'};
    % Tagged runs (submit.sh FID_TAG) are compared with the real-toolbox run too.
    extra = dir(fullfile(casedir, 'real-*'));
    for k = 1:numel(extra), pairs(end+1, :) = {extra(k).name, 'real', 'all'}; end %#ok<AGROW>
    files = {'vasc_only', 'bothat', 'vesselness', 'R_0', 'tfs', 'lfs1', 'chi1', 'lfs2', 'chi2', 'chimap'};
    T = struct('a', {}, 'b', {}, 'output', {}, 'nrmse_pct', {}, 'maxabs', {}, 'dice', {}, 'ndiff', {}, ...
               'frac_a', {}, 'frac_b', {});
    for p = 1:size(pairs, 1)
        A = pairs{p, 1}; B = pairs{p, 2}; F = pairs{p, 3};
        if ischar(F), F = files; end
        for k = 1:numel(F)
            fa = locate(casedir, A, F{k}); fb = locate(casedir, B, F{k});
            if isempty(fa) || isempty(fb), continue; end
            a = rd(fa); b = rd(fb);
            r = struct('a', A, 'b', B, 'output', F{k}, 'nrmse_pct', NaN, 'maxabs', max(abs(a(:) - b(:))), ...
                       'dice', NaN, 'ndiff', nnz(a ~= b), 'frac_a', NaN, 'frac_b', NaN);
            nb = norm(b(mask));
            if nb > 0, r.nrmse_pct = 100 * norm(a(mask) - b(mask)) / nb; end
            if strcmp(F{k}, 'vasc_only') || strcmp(F{k}, 'R_0')
                sa = mask & a < 0.5; sb = mask & b < 0.5;
                r.dice = 2 * nnz(sa & sb) / (nnz(sa) + nnz(sb));   % NaN when both sets are empty
                r.frac_a = nnz(sa) / nnz(mask); r.frac_b = nnz(sb) / nnz(mask);
            end
            T(end+1) = r; %#ok<AGROW>
        end
    end
    thr = struct();
    res = struct();
    for run = [{'container', 'real', 'real2'}, {extra.name}]
        j = fullfile(casedir, run{1}, 'intermediates', 'intermediates.json');
        if exist(j, 'file')
            v = jsondecode(fileread(j));
            thr.(strrep(run{1}, '-', '_')) = v.otsu_threshold;
            if isfield(v, 'resolved'), res.(strrep(run{1}, '-', '_')) = v.resolved; end
        end
    end
    fid = fopen(strrep(outmd, '.md', '.json'), 'w');
    fwrite(fid, jsonencode(struct('rows', T, 'otsu', thr), 'PrettyPrint', true)); fclose(fid);

    fid = fopen(outmd, 'w'); c = onCleanup(@() fclose(fid));
    fprintf(fid, '| Run | vs | Output | NRMSE (%%) | Max abs diff | Dice | Differing voxels | Set fraction of mask (run / vs) |\n');
    fprintf(fid, '|---|---|---|---|---|---|---|---|\n');
    for r = T
        d = ''; fr = '';
        if ~isnan(r.frac_a), fr = sprintf('%.4f / %.4f', r.frac_a, r.frac_b); d = 'both empty'; end
        if ~isnan(r.dice), d = sprintf('%.6f', r.dice); end
        fprintf(fid, '| %s | %s | `%s` | %s | %s | %s | %d | %s |\n', r.a, r.b, r.output, ...
            num(r.nrmse_pct), num(r.maxabs), d, r.ndiff, fr);
    end
    f = fieldnames(thr);
    if ~isempty(f)
        fprintf(fid, '\nOtsu threshold on the vesselness: ');
        fprintf(fid, '%s\n', strjoin(cellfun(@(n) sprintf('%s %.10g', n, thr.(n)), f, 'UniformOutput', false), ', '));
    end

    % Where each toolbox function resolved, per run (recon.m records it with the intermediates).
    for f = fieldnames(res)'
        fprintf(fid, '\nToolbox functions as `%s` resolved them:\n\n', f{1});
        r = res.(f{1});
        for n = fieldnames(r)', fprintf(fid, '- `%s`: `%s`\n', n{1}, r.(n{1})); end
    end
    fprintf('%s\n', fileread(outmd));
end

function f = locate(casedir, run, name)
    f = fullfile(casedir, run, 'intermediates', [name '.nii.gz']);
    if exist(f, 'file'), return; end
    f = fullfile(casedir, run, [name '.nii.gz']);
    if ~exist(f, 'file'), f = ''; end
end

function a = rd(f)
    t = [tempname '.nii'];
    system(sprintf('gunzip -c ''%s'' > ''%s''', f, t));
    n = load_untouch_nii(t); delete(t);
    a = double(n.img);
    s = double(n.hdr.dime.scl_slope);
    if s ~= 0 && ~(s == 1 && n.hdr.dime.scl_inter == 0)
        a = a * s + double(n.hdr.dime.scl_inter);
    end
end

function s = num(x)
    if isnan(x), s = 'n/a'; elseif x == 0, s = '0'; else, s = sprintf('%.3g', x); end
end
