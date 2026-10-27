function pass = compare_runs(casedir, maskfile, outmd)
% Compare the runs of one case (QSMxT/QSM-CI#295, container fidelity).
%   casedir/<run>/*.nii.gz and casedir/<run>/intermediates/*.nii.gz, for the runs
%     container    the pinned image on Apptainer (its intermediates if recon.m writes them)
%     real, real2  licensed MATLAB with the real toolboxes, twice (the run-to-run floor)
%     real-<tag>   a licensed run with another algorithm copy or other sources (submit.sh FID_TAG)
%   maskfile  the case's mask.nii.gz (NRMSE is taken inside it)
% Every output of `real` is compared: the container's, real2's and each real-<tag>'s.
% Metrics: NRMSE % = 100 ||a - b|| / ||b|| inside the mask, b = real; max |a - b| over the volume;
% the number of differing voxels; Dice of the a > 0.5 sets inside the mask when both are binary.
% PASS: every output real writes exists in the container run and no voxel of it differs.
% Writes OUTMD (a Markdown table) and the same rows as JSON next to it.
    mask = rd(maskfile) > 0.5;
    ref = 'real';
    files = outputs(fullfile(casedir, ref));
    runs = {'container', 'real2'};
    extra = dir(fullfile(casedir, 'real-*'));
    runs = [runs, {extra.name}];
    T = struct('a', {}, 'b', {}, 'output', {}, 'nrmse_pct', {}, 'maxabs', {}, 'dice', {}, 'ndiff', {}, ...
               'nvox', {});
    pass = true; missing = {};
    % An image built before recon.m wrote intermediates gives the final outputs only.
    nointer = ~exist(fullfile(casedir, 'container', 'intermediates'), 'dir');
    for r = runs
        if ~exist(fullfile(casedir, r{1}), 'dir'), continue; end
        for k = 1:numel(files)
            fa = locate(casedir, r{1}, files{k}); fb = locate(casedir, ref, files{k});
            if isempty(fa) && strcmp(r{1}, 'container') && nointer && startsWith(files{k}, 'intermediates')
                continue;
            end
            if isempty(fa)
                if strcmp(r{1}, 'container'), pass = false; missing{end+1} = files{k}; end %#ok<AGROW>
                continue;
            end
            a = rd(fa); b = rd(fb);
            row = struct('a', r{1}, 'b', ref, 'output', files{k}, 'nrmse_pct', NaN, 'maxabs', NaN, ...
                         'dice', NaN, 'ndiff', NaN, 'nvox', numel(b));
            if ~isequal(size(a), size(b))
                row.ndiff = numel(b);
            else
                d = a(:) - b(:);
                d(isnan(a(:)) & isnan(b(:))) = 0;
                row.maxabs = max(abs(d));
                row.ndiff = nnz(~(a(:) == b(:) | (isnan(a(:)) & isnan(b(:)))));
                m = repmat(mask, [1 1 1 size(b, 4)]);
                nb = norm(b(m));
                if nb > 0, row.nrmse_pct = 100 * norm(a(m) - b(m)) / nb; end
                if isbin(a) && isbin(b)
                    sa = m & a > 0.5; sb = m & b > 0.5;
                    row.dice = 2 * nnz(sa & sb) / (nnz(sa) + nnz(sb));
                end
            end
            if strcmp(r{1}, 'container') && row.ndiff ~= 0, pass = false; end
            T(end+1) = row; %#ok<AGROW>
        end
    end

    % intermediates.json of each run: scalars, thread count, where the toolbox functions resolved
    meta = struct();
    for r = [{ref}, runs]
        j = fullfile(casedir, r{1}, 'intermediates', 'intermediates.json');
        if exist(j, 'file'), meta.(matlab.lang.makeValidName(r{1})) = jsondecode(fileread(j)); end
    end
    fid = fopen(strrep(outmd, '.md', '.json'), 'w');
    fwrite(fid, jsonencode(struct('pass', pass, 'missing', {missing}, 'rows', T, 'meta', meta), ...
        'PrettyPrint', true));
    fclose(fid);

    fid = fopen(outmd, 'w'); c = onCleanup(@() fclose(fid));
    if pass, verdict = 'PASS (container identical to licensed MATLAB)'; else, verdict = 'FAIL'; end
    fprintf(fid, '%s\n\n', verdict);
    if nointer, fprintf(fid, 'The container run wrote no intermediates: final outputs only.\n\n'); end
    if ~isempty(missing)
        fprintf(fid, 'Missing from the container run: %s\n\n', strjoin(missing, ', '));
    end
    fprintf(fid, '| Run | vs | Output | NRMSE (%%) | Max abs diff | Differing voxels | Dice |\n');
    fprintf(fid, '|---|---|---|---|---|---|---|\n');
    for r = T
        d = ''; if ~isnan(r.dice), d = sprintf('%.6f', r.dice); end
        fprintf(fid, '| %s | %s | `%s` | %s | %s | %d of %d | %s |\n', r.a, r.b, r.output, ...
            num(r.nrmse_pct), num(r.maxabs), r.ndiff, r.nvox, d);
    end
    for f = fieldnames(meta)'
        fprintf(fid, '\n`%s` intermediates.json:\n\n', f{1});
        v = meta.(f{1});
        for n = fieldnames(v)'
            x = v.(n{1});
            if isstruct(x)
                fprintf(fid, '- `%s`:\n', n{1});
                for m = fieldnames(x)', fprintf(fid, '  - `%s`: `%s`\n', m{1}, val(x.(m{1}))); end
            else
                fprintf(fid, '- `%s`: `%s`\n', n{1}, val(x));
            end
        end
    end
    fprintf('%s\n', fileread(outmd));
end

function f = outputs(d)
% NIfTI outputs of a run: the top level and intermediates/, as paths relative to the run folder.
    f = {};
    for sub = {'', 'intermediates'}
        l = dir(fullfile(d, sub{1}, '*.nii.gz'));
        for k = 1:numel(l), f{end+1} = fullfile(sub{1}, l(k).name); end %#ok<AGROW>
    end
end

function f = locate(casedir, run, name)
    f = fullfile(casedir, run, name);
    if ~exist(f, 'file'), f = ''; end
end

function b = isbin(a)
    b = all(a(:) == 0 | a(:) == 1);
end

function a = rd(f)
    info = niftiinfo(f);
    a = double(niftiread(info));
    s = double(info.MultiplicativeScaling); o = double(info.AdditiveOffset);
    if s ~= 0 && ~(s == 1 && o == 0), a = a * s + o; end
end

function s = num(x)
    if isnan(x), s = 'n/a'; elseif x == 0, s = '0'; else, s = sprintf('%.3g', x); end
end

function s = val(x)
    if ischar(x), s = x; elseif isnumeric(x) || islogical(x), s = mat2str(x, 10); else, s = jsonencode(x); end
end
