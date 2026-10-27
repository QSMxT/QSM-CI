function R = shim_fidelity(shimdir, outdir, depsdir)
% Shim fidelity (QSMxT/QSM-CI#295, step 1): call every shim in SHIMDIR and the licensed toolbox
% function it stands in for on the same inputs, and compare.
%
%   shim_fidelity(shimdir, outdir)            synthetic cases only
%   shim_fidelity(shimdir, outdir, depsdir)   + graythresh on real Frangi vesselness
%                                             (depsdir from assemble_deps.sh, mex built)
%
% Run in licensed MATLAB with the Image Processing and Statistics toolboxes and WITHOUT shims/ on
% the path. The shims are loaded under other names (shim_<name>, fidelity_shim_copies.m).
%
% Inputs follow how QSMART calls each function (caller column in the report): 3-D volumes, even
% and odd sizes, a brain mask that touches the FOV (cropped slabs), double and logical masks,
% sphere radii 1/2/5/8, imgaussian's 1-D kernels, the SDF Gaussian sigmas and filter sizes,
% percentiles 99 and 2, graythresh on vesselness-like data.
%
% Pass rule: identical for strel, padarray, morphology and graythresh (no arithmetic that could
% legitimately round differently); max relative error <= 1e-10 for the linear filters (imfilter,
% imgaussfilt3; 1e-5 for single-precision inputs) and 1e-12 for prctile. Cases marked "outside" are forms the shim does not claim to
% support; they are reported for information and do not affect PASS.
%
% Writes OUTDIR/shim_fidelity.json and OUTDIR/shim_fidelity.md.

    if nargin < 3, depsdir = ''; end
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    env = fidelity_env();
    assert(~isempty(env.images) && ~isempty(env.stats), ...
        'shim_fidelity needs the Image Processing and Statistics toolboxes');
    d = dir(fullfile(shimdir, '*.m')); shimnames = erase({d.name}, '.m');
    for k = 1:numel(shimnames)
        w = which(shimnames{k});
        assert(startsWith(w, fullfile(matlabroot, 'toolbox')), ...
            '%s resolves to %s, not the toolbox: remove shims/ from the path', shimnames{k}, w);
    end

    tmp = tempname; fidelity_shim_copies(shimdir, tmp);
    addpath(tmp); cleaner = onCleanup(@() rmpath(tmp));
    if ~isempty(depsdir), addpath(fullfile(depsdir, 'frangi')); end

    rng(0, 'twister');
    C = build_cases(depsdir);
    rows = struct([]);
    for k = 1:numel(C)
        c = C(k);
        fprintf('[%2d/%d] %-12s %s\n', k, numel(C), c.fn, c.desc);
        row = struct('shim', c.fn, 'case', c.desc, 'caller', c.caller, 'scope', c.scope, ...
                     'tol', c.tol, 'status', '', 'error', '', 'cmp', [], 'cmp_inmask', [], ...
                     't_ref', NaN, 't_shim', NaN);
        try
            a = resolve(c.args, 'ref'); t = tic; ref = feval(c.fn, a{:}); row.t_ref = toc(t);
        catch e
            row.status = 'SKIP'; row.error = ['toolbox: ' e.message]; rows = [rows row]; continue %#ok<AGROW>
        end
        try
            a = resolve(c.args, 'shim'); t = tic; got = feval(['shim_' c.fn], a{:}); row.t_shim = toc(t);
        catch e
            row.status = 'FAIL'; row.error = ['shim: ' e.message];
            if ~strcmp(c.scope, 'used'), row.status = 'INFO'; end
            rows = [rows row]; continue %#ok<AGROW>
        end
        row.cmp = fidelity_compare(got, ref);
        if ~isempty(c.inmask) && isequal(size(got), size(ref))
            row.cmp_inmask = fidelity_compare(double(got) .* c.inmask, double(ref) .* c.inmask);
        end
        if c.tol == 0, ok = row.cmp.identical; else, ok = row.cmp.maxrel <= c.tol; end
        if ~strcmp(c.scope, 'used')
            row.status = 'INFO';
        elseif ok
            row.status = 'PASS';
        else
            row.status = 'FAIL';
        end
        if strcmp(c.fn, 'graythresh')
            row.error = sprintf('level shim %.10g, toolbox %.10g', double(got), double(ref));
        end
        rows = [rows row]; %#ok<AGROW>
    end

    R = struct('env', env, 'shim_sha256', shim_hashes(shimdir), 'cases', rows);
    R.summary = summarise(rows, shimnames);
    fid = fopen(fullfile(outdir, 'shim_fidelity.json'), 'w');
    fwrite(fid, jsonencode(R, 'PrettyPrint', true)); fclose(fid);
    write_markdown(R, fullfile(outdir, 'shim_fidelity.md'));
    fprintf('\n%s\n', fileread(fullfile(outdir, 'shim_fidelity.md')));
end

% ------------------------------------------------------------------------------------------------
function C = build_cases(depsdir)
    C = struct('fn', {}, 'desc', {}, 'caller', {}, 'args', {}, 'tol', {}, 'scope', {}, 'inmask', {});
    EXACT = 0; LIN = 1e-10; PCT = 1e-12; LIN1 = 1e-5;   % LIN1: single-precision inputs
    szE = [96 112 80]; szO = [97 111 79]; szS = [40 36 32];
    mE = brain_mask(szE, false); mO = brain_mask(szO, false); mT = brain_mask(szO, true);
    mS = brain_mask(szS, false);
    [magE, vesE] = magnitude(szE, mE, false);
    [magT, vesT] = magnitude(szO, mT, true);
    grey = rand(szO);

    % strel: QSMART_SDF / vasculature_mask (8), calculate_curvature (1, 5); 2 is what STI's
    % iLSQR/SMV-style erosions use in the sibling containers.
    for r = [1 2 5 8]
        C(end+1) = mk('strel', sprintf('sphere r=%d', r), strel_caller(r), {'sphere', r}, EXACT, 'used', []); %#ok<AGROW>
    end
    C(end+1) = mk('strel', 'disk r=3', 'none in QSMART', {'disk', 3}, EXACT, 'outside', []);

    % padarray: recon.m pads phase/magnitude (4-D) and mask (3-D) to even dims, 'post'.
    C(end+1) = mk('padarray', '4-D phase, [1 1 1], 0, post', 'recon.m (odd dims)', ...
        {randn([szO 4]), [1 1 1], 0, 'post'}, EXACT, 'used', []);
    C(end+1) = mk('padarray', '4-D phase, [0 0 0], 0, post', 'recon.m (even dims)', ...
        {randn([szE 4]), [0 0 0], 0, 'post'}, EXACT, 'used', []);
    C(end+1) = mk('padarray', '3-D mask, [1 0 1], 0, post', 'recon.m', ...
        {double(mO), [1 0 1], 0, 'post'}, EXACT, 'used', []);
    C(end+1) = mk('padarray', 'logical, [3 4 5] both', 'STI Suite (generic form)', ...
        {mO, [3 4 5]}, EXACT, 'used', []);
    C(end+1) = mk('padarray', 'double, [2 2 2], pre', 'generic form', {grey, [2 2 2], 'pre'}, EXACT, 'used', []);
    C(end+1) = mk('padarray', 'double, [2 0 3], 2.5, both', 'generic form', {grey, [2 0 3], 2.5, 'both'}, EXACT, 'used', []);
    for meth = {'replicate', 'symmetric', 'circular'}
        C(end+1) = mk('padarray', ['[2 2 2], ' meth{1}], 'none in QSMART', {grey, [2 2 2], meth{1}}, EXACT, 'outside', []); %#ok<AGROW>
    end

    % imdilate / imerode: calculate_curvature on the DOUBLE 0/1 mask (greyscale path).
    C(end+1) = mk('imdilate', 'double mask, sphere 5, even', 'calculate_curvature', {double(mE), se('sphere', 5)}, EXACT, 'used', []);
    C(end+1) = mk('imdilate', 'double mask, sphere 5, odd', 'calculate_curvature', {double(mO), se('sphere', 5)}, EXACT, 'used', []);
    C(end+1) = mk('imdilate', 'double mask touching FOV, sphere 5', 'calculate_curvature', {double(mT), se('sphere', 5)}, EXACT, 'used', []);
    for r = [1 2 5]
        C(end+1) = mk('imdilate', sprintf('logical mask touching FOV, sphere %d', r), 'STI Suite / generic', {mT, se('sphere', r)}, EXACT, 'used', []); %#ok<AGROW>
    end
    C(end+1) = mk('imdilate', 'random double, sphere 2', 'generic greyscale', {grey, se('sphere', 2)}, EXACT, 'used', []);
    C(end+1) = mk('imerode', 'double mask, sphere 1, even', 'calculate_curvature', {double(mE), se('sphere', 1)}, EXACT, 'used', []);
    C(end+1) = mk('imerode', 'double mask, sphere 1, odd', 'calculate_curvature', {double(mO), se('sphere', 1)}, EXACT, 'used', []);
    C(end+1) = mk('imerode', 'double mask touching FOV, sphere 1', 'calculate_curvature', {double(mT), se('sphere', 1)}, EXACT, 'used', []);
    for r = [1 2 5]
        C(end+1) = mk('imerode', sprintf('logical mask touching FOV, sphere %d', r), 'STI Suite / generic', {mT, se('sphere', r)}, EXACT, 'used', []); %#ok<AGROW>
    end
    C(end+1) = mk('imerode', 'random double, sphere 2', 'generic greyscale', {grey, se('sphere', 2)}, EXACT, 'used', []);

    % imclose: QSMART_SDF fills inward indents of the DOUBLE mask with sphere 8.
    C(end+1) = mk('imclose', 'double mask, sphere 8, even', 'QSMART_SDF', {double(mE), se('sphere', 8)}, EXACT, 'used', []);
    C(end+1) = mk('imclose', 'double mask, sphere 8, odd', 'QSMART_SDF', {double(mO), se('sphere', 8)}, EXACT, 'used', []);
    C(end+1) = mk('imclose', 'double mask touching FOV, sphere 8', 'QSMART_SDF', {double(mT), se('sphere', 8)}, EXACT, 'used', []);
    C(end+1) = mk('imclose', 'logical mask touching FOV, sphere 8', 'brainmask.m (generic)', {mT, se('sphere', 8)}, EXACT, 'used', []);
    C(end+1) = mk('imopen', 'logical mask touching FOV, sphere 2', 'generic', {mT, se('sphere', 2)}, EXACT, 'used', []);
    C(end+1) = mk('imopen', 'double mask, sphere 2, odd', 'generic', {double(mO), se('sphere', 2)}, EXACT, 'used', []);
    C(end+1) = mk('imopen', 'double mask touching FOV, sphere 5', 'generic', {double(mT), se('sphere', 5)}, EXACT, 'used', []);
    C(end+1) = mk('imopen', 'random double, sphere 2', 'generic greyscale', {grey, se('sphere', 2)}, EXACT, 'used', []);
    C(end+1) = mk('imclose', 'random double, sphere 2', 'generic greyscale', {grey, se('sphere', 2)}, EXACT, 'used', []);

    % imbothat: vasculature mask on the (N4-corrected) mean-echo magnitude, sphere 8. The
    % magnitude fills the FOV (noise outside the head), so the FOV border matters; QSMART then
    % multiplies by the brain mask, so the in-mask error is reported too.
    C(end+1) = mk('imbothat', 'magnitude, sphere 8, even', 'vasculature_mask', {magE, se('sphere', 8)}, EXACT, 'used', double(mE));
    C(end+1) = mk('imbothat', 'magnitude, brain touching FOV, sphere 8', 'vasculature_mask', {magT, se('sphere', 8)}, EXACT, 'used', double(mT));
    C(end+1) = mk('imbothat', 'single magnitude (as the original runs), sphere 8', 'vasculature_mask (original, N4 output float32)', ...
        {single(magT), se('sphere', 8)}, EXACT, 'used', double(mT));

    % imfilter: Frangi's imgaussian.m, imfilter(I, H, 'same', 'replicate') with 1-D kernels
    % along x, y, z; siz = 6*sigma for the Frangi scales 0.5:0.5:6.
    for s = [0.5 2 6]
        for d = 1:3
            C(end+1) = mk('imfilter', sprintf('sigma %.1f kernel along dim %d', s, d), 'imgaussian (Frangi Hessian)', ...
                {magE .* mE, gk(s, d), 'same', 'replicate'}, LIN, 'used', []); %#ok<AGROW>
        end
    end
    C(end+1) = mk('imfilter', 'single input, sigma 2, dim 3', 'imgaussian (original single precision)', ...
        {single(magT .* mT), gk(2, 3), 'same', 'replicate'}, LIN1, 'used', []);
    C(end+1) = mk('imfilter', 'kernel longer than the dim (sigma 6, 32 slices)', 'imgaussian', ...
        {rand(szS), gk(6, 3), 'same', 'replicate'}, LIN, 'used', []);
    C(end+1) = mk('imfilter', '3-D kernel, conv', 'none in QSMART (Hessian2D only)', ...
        {grey, rand(3, 3, 3), 'conv'}, LIN, 'outside', []);

    % imgaussfilt3: sdf_curvature / calculate_curvature, as called for stage 1 (sigma1 = 10) and
    % stage 2 (sigma1 = 8, sigma2 = 2); SDF kernels A(i) in (0, sigma] at filterSize
    % 2*ceil(2*sigma)+1 (sigma = sqrt(sigma1^2+sigma2^2): 14.14 -> 59, 8.25 -> 35).
    tfs = smooth3(randn(szO), 'gaussian', [9 9 9], 3) .* mO;
    C(end+1) = mk('imgaussfilt3', 'mask, [10 20 20]', 'sdf_curvature prox1 (stage 1)', {double(mO), [10 20 20]}, LIN, 'used', []);
    C(end+1) = mk('imgaussfilt3', 'mask touching FOV, [8 16 16]', 'sdf_curvature prox1 (stage 2)', {double(mT), [8 16 16]}, LIN, 'used', []);
    C(end+1) = mk('imgaussfilt3', 'vessel mask, 2', 'sdf_curvature prox2 (stage 2)', {double(~vesT), 2}, LIN, 'used', []);
    C(end+1) = mk('imgaussfilt3', 'curvature image, [10 20 20]', 'calculate_curvature prox3', {1 - 0.5 * double(mO) .* rand(szO), [10 20 20]}, LIN, 'used', []);
    C(end+1) = mk('imgaussfilt3', 'edge proximity, [5 10 10]', 'calculate_curvature prox4', {double(mO) .* rand(szO), [5 10 10]}, LIN, 'used', []);
    for a = [0.14 3.5 14.14]
        C(end+1) = mk('imgaussfilt3', sprintf('tfs.*mask, %.2f, filterSize 59', a), 'sdf_curvature num (stage 1)', ...
            {tfs, a, 'filterSize', 59}, LIN, 'used', []); %#ok<AGROW>
    end
    C(end+1) = mk('imgaussfilt3', 'mask, 8.25, filterSize 35', 'sdf_curvature denum (stage 2)', {double(mT), 8.25, 'filterSize', 35}, LIN, 'used', []);
    C(end+1) = mk('imgaussfilt3', 'small volume, [10 20 20] (kernel > dims)', 'sdf_curvature (small FOV)', {double(mS), [10 20 20]}, LIN, 'used', []);
    C(end+1) = mk('imgaussfilt3', 'single input, 2', 'none (recon passes double)', {single(double(~vesT)), 2}, LIN1, 'outside', []);

    % graythresh: Otsu on the Frangi vesselness (values in [0, 1], mostly zero).
    v = zeros(szO); v(vesT & mT) = 0.05 + 0.5 * rand(nnz(vesT & mT), 1) .^ 2;
    v(mT & ~vesT) = 1e-4 * rand(nnz(mT & ~vesT), 1);
    C(end+1) = mk('graythresh', 'vesselness-like', 'vasculature_mask', {v}, EXACT, 'used', []);
    C(end+1) = mk('graythresh', 'vesselness-like x 1e-3 (all < 1/510)', 'vasculature_mask (phantom: T = 0)', {v * 1e-3}, EXACT, 'used', []);
    C(end+1) = mk('graythresh', 'uniform [0,1]', 'generic', {rand(szS)}, EXACT, 'used', []);
    C(end+1) = mk('graythresh', 'values on k/255', 'generic', {randi([0 255], szS) / 255}, EXACT, 'used', []);
    C(end+1) = mk('graythresh', 'single vesselness-like', 'vasculature_mask (original single)', {single(v)}, EXACT, 'used', []);
    C(end+1) = mk('graythresh', 'all zero', 'generic', {zeros(szS)}, EXACT, 'used', []);
    if ~isempty(depsdir) && exist('FrangiFilter3D', 'file')
        opts = struct('FrangiScaleRange', [0.5 6], 'FrangiScaleRatio', 0.5, 'FrangiAlpha', 0.5, ...
                      'FrangiBeta', 0.5, 'FrangiC', 500, 'verbose', false, 'BlackWhite', false);
        bh = imbothat(magT, strel('sphere', 8));                         % toolbox (shims off path)
        enh = FrangiFilter3D(bh .* mT, opts);
        enh1 = FrangiFilter3D(single(bh) .* single(mT), opts);
        C(end+1) = mk('graythresh', 'Frangi vesselness (double)', 'vasculature_mask', {enh}, EXACT, 'used', []);
        C(end+1) = mk('graythresh', 'Frangi vesselness (single, as the original)', 'vasculature_mask', {enh1}, EXACT, 'used', []);
    end

    % prctile: echofit / brainmask adaptive thresholds (off by default): a vector of non-zero
    % blurred residuals, percentiles 99 and 2.
    res = exp(randn(200000, 1));
    C(end+1) = mk('prctile', 'residuals, 99', 'echofit (adaptive_threshold)', {res, 99}, PCT, 'used', []);
    C(end+1) = mk('prctile', 'residuals, 2', 'brainmask (mag_thresh_percentile)', {res, 2}, PCT, 'used', []);
    C(end+1) = mk('prctile', 'row vector, [2 99]', 'generic', {res(1:1001)', [2 99]}, PCT, 'used', []);
    C(end+1) = mk('prctile', 'n = 3, 99', 'generic', {[3; 1; 2], 99}, PCT, 'used', []);
    C(end+1) = mk('prctile', 'ties, 50', 'generic', {[1; 1; 1; 2; 2], 50}, PCT, 'used', []);
    C(end+1) = mk('prctile', 'matrix (column-wise), 99', 'none in QSMART', {rand(50, 4), 99}, PCT, 'outside', []);
end

function s = strel_caller(r)
    switch r
        case {1, 5}, s = 'calculate_curvature';
        case 8, s = 'QSMART_SDF, vasculature_mask';
        otherwise, s = 'STI Suite / generic';
    end
end

function c = mk(fn, desc, caller, args, tol, scope, inmask)
    c = struct('fn', fn, 'desc', desc, 'caller', caller, 'args', {args}, 'tol', tol, ...
               'scope', scope, 'inmask', inmask);
end

function s = se(varargin), s = struct('qsmci_se', {varargin}); end

function a = resolve(a, side)
% Structuring-element placeholders become the toolbox strel or the shim's struct.
    for k = 1:numel(a)
        if isstruct(a{k}) && isfield(a{k}, 'qsmci_se')
            if strcmp(side, 'ref'), a{k} = strel(a{k}.qsmci_se{:}); else, a{k} = shim_strel(a{k}.qsmci_se{:}); end
        end
    end
end

function H = gk(sigma, d)
% imgaussian.m's kernel: x = -ceil(siz/2):ceil(siz/2), siz = 6*sigma, oriented along dim d.
    siz = sigma * 6; x = -ceil(siz / 2):ceil(siz / 2);
    H = exp(-(x .^ 2 / (2 * sigma ^ 2))); H = H / sum(H(:));
    shape = [1 1 1]; shape(d) = numel(H); H = reshape(H, shape);
end

function m = brain_mask(sz, touch)
% Lobed ellipsoid with an inward groove (something for the sphere-8 closing to fill). TOUCH
% stretches it past both z faces of the FOV, as in a cropped axial slab.
    [x, y, z] = ndgrid(linspace(-1, 1, sz(1)), linspace(-1, 1, sz(2)), linspace(-1, 1, sz(3)));
    a = [0.78 0.85 0.75]; if touch, a(3) = 1.15; end
    n = smooth3(randn(sz), 'gaussian', [9 9 9], 3); n = 0.08 * n / max(abs(n(:)));
    m = sqrt((x / a(1)) .^ 2 + (y / a(2)) .^ 2 + (z / a(3)) .^ 2) + n < 1;
    m(x > 0.45 & abs(y) < 0.07) = false;
end

function [mag, ves] = magnitude(sz, m, touch)
% Mean-echo-like magnitude: Rician noise outside the head, smooth bias inside, dark tubes.
    [x, y, z] = ndgrid(linspace(-1, 1, sz(1)), linspace(-1, 1, sz(2)), linspace(-1, 1, sz(3)));
    a = [0.9 0.97 0.88]; if touch, a(3) = 1.3; end
    head = sqrt((x / a(1)) .^ 2 + (y / a(2)) .^ 2 + (z / a(3)) .^ 2) < 1;
    bias = 0.8 + 0.2 * smooth3(randn(sz), 'gaussian', [15 15 15], 6) * 20;
    mag = 0.03 * abs(randn(sz) + 1i * randn(sz));
    mag(head) = 0.5 * bias(head) + 0.02 * randn(nnz(head), 1);
    mag(m) = mag(m) + 0.2;
    ves = false(sz);
    P = [x(:) y(:) z(:)];
    for k = 1:14
        p0 = (rand(1, 3) - 0.5) * 1.2; dv = randn(1, 3); dv = dv / norm(dv);
        t = (P - p0) * dv'; t = max(-0.6, min(0.6, t));
        d = sqrt(sum((P - (p0 + t * dv)) .^ 2, 2)) * sz(1) / 2;
        ves(d < 1.0 + 0.6 * rand) = true;
    end
    ves = ves & head;
    mag(ves) = 0.35 * mag(ves);
end

function S = summarise(rows, names)
    S = struct('shim', {}, 'status', {}, 'used_cases', {}, 'failed', {}, 'worst_maxabs', {}, 'worst_maxrel', {});
    for k = 1:numel(names)
        r = rows(strcmp({rows.shim}, names{k}) & strcmp({rows.scope}, 'used'));
        f = r(strcmp({r.status}, 'FAIL'));
        ma = 0; mr = 0;
        for j = 1:numel(r)
            if ~isempty(r(j).cmp), ma = max(ma, r(j).cmp.maxabs); mr = max(mr, r(j).cmp.maxrel); end
        end
        st = 'PASS'; if ~isempty(f), st = 'FAIL'; end
        if isempty(r), st = 'NOT TESTED'; end
        S(end+1) = struct('shim', names{k}, 'status', st, 'used_cases', numel(r), ...
                          'failed', numel(f), 'worst_maxabs', ma, 'worst_maxrel', mr); %#ok<AGROW>
    end
end

function h = shim_hashes(shimdir)
    h = struct();
    d = dir(fullfile(shimdir, '*.m'));
    for k = 1:numel(d)
        [~, o] = system(sprintf('sha256sum ''%s''', fullfile(shimdir, d(k).name)));
        h.(erase(d(k).name, '.m')) = strtok(o);
    end
end

function write_markdown(R, f)
    fid = fopen(f, 'w'); c = onCleanup(@() fclose(fid));
    e = R.env;
    fprintf(fid, 'MATLAB %s; Image Processing Toolbox %s; Statistics and Machine Learning Toolbox %s; %s on %s.\n\n', ...
        e.matlab, e.images, e.stats, e.date, e.host);
    fprintf(fid, '| Shim | Status | Cases (used forms) | Failed | Worst max abs error | Worst max rel error |\n');
    fprintf(fid, '|---|---|---|---|---|---|\n');
    for s = R.summary
        fprintf(fid, '| `%s` | %s | %d | %d | %s | %s |\n', s.shim, s.status, s.used_cases, s.failed, ...
            num(s.worst_maxabs), num(s.worst_maxrel));
    end
    fprintf(fid, '\n<details><summary>Every case</summary>\n\n');
    fprintf(fid, '| Shim | Case | QSMART caller | Status | Identical | Max abs | Max rel | Differing elements | In-mask max abs | Tolerance | Note |\n');
    fprintf(fid, '|---|---|---|---|---|---|---|---|---|---|---|\n');
    for r = R.cases
        if isempty(r.cmp)
            fprintf(fid, '| `%s` | %s | %s | %s | | | | | | | %s |\n', r.shim, r.case, r.caller, r.status, r.error);
            continue
        end
        im = ''; if ~isempty(r.cmp_inmask), im = num(r.cmp_inmask.maxabs); end
        tol = 'identical'; if r.tol > 0, tol = sprintf('rel %g', r.tol); end
        note = r.error;
        if ~strcmp(r.cmp.class_got, r.cmp.class_ref)
            note = strtrim(sprintf('%s class %s vs %s', note, r.cmp.class_got, r.cmp.class_ref));
        end
        if ~strcmp(r.scope, 'used'), note = strtrim(['outside the shim''s forms. ' note]); end
        fprintf(fid, '| `%s` | %s | %s | %s | %s | %s | %s | %d / %d | %s | %s | %s |\n', r.shim, r.case, ...
            r.caller, r.status, yn(r.cmp.identical), num(r.cmp.maxabs), num(r.cmp.maxrel), ...
            r.cmp.ndiff, r.cmp.numel, im, tol, note);
    end
    fprintf(fid, '\n</details>\n');
end

function s = num(x)
    if x == 0, s = '0'; else, s = sprintf('%.3g', x); end
end

function s = yn(b)
    if b, s = 'yes'; else, s = 'no'; end
end
