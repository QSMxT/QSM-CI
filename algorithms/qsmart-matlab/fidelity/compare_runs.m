function T = compare_runs(casedir, maskfile, deps, outmd)
% Container fidelity (QSMxT/QSM-CI#295, step 2): compare the runs of one case.
%   casedir/<run>/chimap.nii.gz and casedir/<run>/intermediates/*.nii.gz, runs:
%     container    the pinned image on Apptainer (with intermediates if the image has the
%                  QSMCI_INTERMEDIATES option, else the final chi only)
%     real, real2  licensed MATLAB with the real toolboxes, twice (run-to-run floor)
%     trace        licensed MATLAB with the shims (+ per-call toolbox comparison)
%     trace-<tag>  trace with another copy of the algorithm folder (submit.sh FID_TAG)
%   maskfile  the case's mask.nii.gz (NRMSE is taken inside it)
% Metrics: NRMSE % = 100 ||a - b|| / ||b|| inside the mask, b the reference run; max |a - b| over
% the volume; Dice for the masks (vessels = mask & ~vasc_only; R_0 rejects = mask & ~R_0), with
% each set's fraction of the brain mask.
    addpath(fullfile(deps, 'nifti'));
    mask = rd(maskfile) > 0.5;
    pairs = {'container', 'real',  'all';
             'container', 'trace', 'all';
             'trace',     'real',  'all';
             'real2',     'real',  'all'};
    % Runs of other algorithm copies (submit.sh FID_TAG, e.g. trace-<tag> with proposed shim
    % fixes) are compared with the real-toolbox run too.
    extra = dir(fullfile(casedir, 'trace-*'));
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
    for run = {'real', 'real2', 'trace'}
        j = fullfile(casedir, run{1}, 'intermediates', 'intermediates.json');
        if exist(j, 'file')
            v = jsondecode(fileread(j));
            thr.(strrep(run{1}, '-', '_')) = v.otsu_threshold;
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

    % Every shim call the pipeline made (trace runs), per shim and call site.
    for t = [{'trace'}, {extra.name}]
        f = fullfile(casedir, t{1}, 'trace', 'trace.tsv');
        if ~exist(f, 'file'), continue; end
        L = readcell(f, 'FileType', 'text', 'Delimiter', '\t', 'NumHeaderLines', 1);
        key = strcat(L(:, 1), '|', L(:, 3));
        [u, ~, g] = unique(key, 'stable');
        fprintf(fid, '\nShim calls in `%s` (%d calls; each also run through the toolbox):\n\n', t{1}, size(L, 1));
        fprintf(fid, '| Shim | Call site | Calls | Not identical | Max abs | Max rel | Example arguments |\n');
        fprintf(fid, '|---|---|---|---|---|---|---|\n');
        for k = 1:numel(u)
            i = find(g == k);
            ma = max(cell2mat(L(i, 8))); mr = max(cell2mat(L(i, 9)));
            fprintf(fid, '| `%s` | %s | %d | %d | %s | %s | `%s` |\n', L{i(1), 1}, L{i(1), 3}, numel(i), ...
                nnz(cell2mat(L(i, 7)) == 0), num(ma), num(mr), L{i(1), 4});
        end
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
