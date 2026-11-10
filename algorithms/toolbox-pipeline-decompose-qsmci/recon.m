function recon(inp, out)
% QSM-CI `pipeline` span in MATLAB: DECOMPOSE-QSM as its paper describes it (Chen et al. 2021,
% NeuroImage 242:118477), from the echoes to χ+ and χ−, as the reference for QSMxT's `decompose`
% pipeline (QSMxT/QSM-CI#421; Ashley 2026-11-10: the paper, not Tim Ho's script). The paper ships
% no code, so this is QSM-CI's MATLAB of it, written to the paper with MATLAB's own solvers:
%
%   §3.6: "QSM reconstruction was performed with functions in STI Suite V3.0. The GRE magnitude
%   images of the first echo was used to mask and extract the brain tissue using ... BET in FSL.
%   The raw phase was unwrapped using a Laplacian-based phase unwrapping method. The background
%   phase was removed with the V-SHARP method. Lastly, STAR-QSM was performed to compute the
%   susceptibility maps for each echo. For the in vivo scans, susceptibility values were
%   referenced to the mean susceptibility of the whole brain."
%   - BET: FSL bet2 (MEDI's bet2 mex is FSL's bet2 code) on echo 1's magnitude, its defaults, with
%     x reversed around it for a neurological header, as FSL's bet does when it reads the file
%     (fsl_bet below); MEDI's BET.m hands the mex the array as stored.
%   - Per echo: MRPhaseUnwrap, V_SHARP and QSM_star (TE of that echo), STI Suite's defaults: the
%     paper states no parameters.
%   - Each echo's χ referenced to its whole-brain mean (inside V-SHARP's mask).
%   §2.2, Eq. 4-5: y(t) = M(t)·exp(−i·(2/3)·χ(t)·γ·B0·t) and the alternating fit, 10 passes:
%   - 5.1 [C+, C−, C0]: lsqlin, interior-point, C+ + C− + C0 = 1, 0 ≤ C ≤ 1, on the complex signal.
%   - 5.2 R2*0: lsqlin, interior-point, R2*0 ≥ 0, on the complex log (linear in R2*0 there).
%   - 5.3 [χ+, χ−]: lsqnonlin, trust-region-reflective, 0 ≤ χ+ ≤ 0.5, −0.5 ≤ χ− ≤ 0, on the log.
%   Each voxel is scaled to S(0) = 1 (the sum-to-one constraint needs it; the paper does not say
%   how): S0 = M1·(M1/M2)^(TE1/(TE2−TE1)), or M1 where the first two echoes do not decay
%   (QSM.rs's DecomposeNormalisation::ExtrapolatedS0, Ashley 2026-11-10). Initial values and
%   tolerances are Tim Ho's script's (C = [.3 .3 .4], R2*0 = 25, χ = [.05 −.05]; MATLAB's
%   defaults), since the paper gives none. Model and reconstruction functions are the vendored
%   decompose_utils (Tim Ho's), as in decompose-qsm. χ+ = |DSC|, χ− = |PSC| (decompose-qsm's
%   output mapping: the fit is to conj(y)).
%
% Intermediates (QSMCI_INTERMEDIATES): mask (BET's), mask_vsharp, chimap_echo<n> (referenced
% per-echo χ, ppm), and the fitted c_plus, c_minus, c_zero, r2star0, chi_plus, chi_minus, for the
% lsqlin cross-check of QSM.rs's exact solves (astewartau/QSM.rs#449).
%
% Toolbox functions STI Suite's pcode calls, which mcc can't trace into: name them so they are
% bundled (../../fidelity/matlab/README.md, `trace`); keep toolbox_functions() below in step.
%#function padarray

    p = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0 = double(p.B0); TE = double(p.TE(:)');
    H = p.B0_dir(:)'; H = H / norm(H);
    vox = p.voxel_size(:)';
    gamma = 42.58 * 2*pi;
    nph = read_niigz(fullfile(inp, 'phase.nii.gz'));
    ph  = double(nph.img);
    nmag = read_niigz(fullfile(inp, 'magnitude.nii.gz'));
    mag = double(nmag.img);
    ne = numel(TE);
    [N1, N2, N3, ~] = size(ph);
    matrix_size = [N1 N2 N3];

    % --- §3.6 ---
    mask = fsl_bet(mag(:,:,:,1), matrix_size, vox, nmag.hdr);
    chi = zeros(N1, N2, N3, ne);
    mask_v = true(N1, N2, N3);
    for e = 1:ne
        uw = MRPhaseUnwrap(ph(:,:,:,e), 'voxelsize', vox);
        [lf, mv] = V_SHARP(uw, mask, 'voxelsize', vox);
        q = QSM_star(lf, mv, 'TE', TE(e) * 1e3, 'B0', B0, 'H', H, 'voxelsize', vox);
        q(mv > 0) = q(mv > 0) - mean(q(mv > 0));
        chi(:,:,:,e) = q .* (mv > 0);
        mask_v = mask_v & (mv > 0);
    end

    % --- §2.2 ---
    N_inner = 10;
    o1 = optimoptions('lsqlin', 'Algorithm', 'interior-point', 'Display', 'off');
    o3 = optimoptions('lsqnonlin', 'Algorithm', 'trust-region-reflective', 'Display', 'off');
    Cp = zeros(N1,N2,N3); Cm = Cp; C0m = Cp; R0m = Cp; chp = Cp; chm = Cp;
    % DECOMPOSE_CROPBOX=n fits only the voxels in an (n+1)^3 central box, as decompose-qsm's
    % fidelity check does: the fit is per voxel and independent between voxels, and the whole
    % brain takes hours. Everything before the fit (mask, per-echo χ) is whole-volume either way.
    fitmask = mask_v;
    box = str2double(getenv('DECOMPOSE_CROPBOX'));
    if ~isnan(box) && box > 0
        sel = false(N1, N2, N3); c = round([N1 N2 N3]/2); h = floor(box/2);
        sel(max(1,c(1)-h):min(N1,c(1)+h), max(1,c(2)-h):min(N2,c(2)+h), max(1,c(3)-h):min(N3,c(3)+h)) = true;
        fitmask = fitmask & sel;
    end
    try
        if isempty(gcp('nocreate'))
            pc = parcluster('local'); jsl = tempname; mkdir(jsl); pc.JobStorageLocation = jsl;
            parpool(pc, feature('numcores'));
        end
    catch err
        fprintf('DECOMPOSE: no parpool (%s), running serially\n', err.message);
    end
    idx = find(fitmask);
    nv = numel(idx);
    fitted = zeros(nv, 6);
    magv = reshape(mag, [], ne); chiv = reshape(chi, [], ne);
    parfor n = 1:nv
        v = idx(n);
        m = magv(v, :);
        s0 = m(1);
        if m(1) > 0 && m(2) > 0 && m(2) < m(1)
            s = m(1) * (m(1)/m(2))^(TE(1)/(TE(2)-TE(1)));
            if isfinite(s), s0 = s; end
        end
        if ~(s0 > 0), continue; end
        % conj(y), as decompose-qsm's `squeeze(y_data(i,j,k,:))'` (the conjugate transpose).
        ydata = conj(m / s0 .* exp(-1i*(2/3) * chiv(v, :) * gamma * B0 .* TE));
        if sum(ydata) == 0, continue; end
        b1 = complex_to_real(ydata);
        b3 = complex_to_real(log(ydata));
        chi_0 = [0.05 -0.05]; R0 = 25; C = [0.3 0.3 0.4];
        for it = 1:N_inner
            A = zeros(numel(b1), 3);
            for c = 1:3
                u = zeros(1, 3); u(c) = 1;
                A(:, c) = complex_to_real(objective1(u, TE, chi_0(1), chi_0(2), R0, B0));
            end
            C = lsqlin(A, b1(:), [], [], [1 1 1], 1, [0 0 0], [1 1 1], C(:), o1)';
            l0 = complex_to_real(objective2(0, TE, C(1), C(2), C(3), chi_0(1), chi_0(2), B0));
            l1 = complex_to_real(objective2(1, TE, C(1), C(2), C(3), chi_0(1), chi_0(2), B0));
            R0 = lsqlin(l1(:) - l0(:), b3(:) - l0(:), [], [], [], [], 0, [], R0, o1);
            f3 = @(x) complex_to_real(objective3(x, TE, C(1), C(2), C(3), R0, B0)) - b3;
            chi_0 = lsqnonlin(f3, chi_0, [0 -0.5], [0.5 0], o3);
        end
        fitted(n, :) = [C(1) C(2) C(3) R0 chi_0(1) chi_0(2)];
    end
    Cp(idx) = fitted(:,1); Cm(idx) = fitted(:,2); C0m(idx) = fitted(:,3);
    R0m(idx) = fitted(:,4); chp(idx) = fitted(:,5); chm(idx) = fitted(:,6);
    den = (2/3) * gamma * B0 * sum(TE);
    PSC = zeros(N1,N2,N3); DSC = PSC;
    for n = 1:nv
        if ~any(fitted(n, :)), continue; end   % skipped: no signal, or no S(0)
        v = idx(n);
        cp = pscModel(TE, Cp(v), Cm(v), C0m(v), chp(v), chm(v), R0m(v), B0);
        cn = dscModel(TE, Cp(v), Cm(v), C0m(v), chp(v), chm(v), R0m(v), B0);
        PSC(v) = -sum(angle(cp)) / den;
        DSC(v) = -sum(angle(cn)) / den;
    end

    tmpl = nph;
    tmpl.hdr.dime.dim(1) = 3;  tmpl.hdr.dime.dim(5) = 1;
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(tmpl, double(mask), fullfile(idir, 'mask.nii.gz'));
        write_intermediate(tmpl, double(mask_v), fullfile(idir, 'mask_vsharp.nii.gz'));
        for e = 1:ne
            write_intermediate(tmpl, chi(:,:,:,e), fullfile(idir, sprintf('chimap_echo%d.nii.gz', e)));
        end
        names = {'c_plus', 'c_minus', 'c_zero', 'r2star0', 'chi_plus', 'chi_minus'};
        maps = {Cp, Cm, C0m, R0m, chp, chm};
        for n = 1:numel(names)
            write_intermediate(tmpl, maps{n}, fullfile(idir, [names{n} '.nii.gz']));
        end
        write_meta(idir, struct('N_inner', N_inner, 'normalisation', 'extrapolated-s0'));
    end
    write_niigz(as_float(tmpl, abs(DSC) .* fitmask), fullfile(out, 'chi-para.nii.gz'));
    write_niigz(as_float(tmpl, abs(PSC) .* fitmask), fullfile(out, 'chi-dia.nii.gz'));
    write_niigz(as_float(tmpl, mean(chi, 4)), fullfile(out, 'chimap.nii.gz'));
end

function m = fsl_bet(img, matrix_size, vox, hdr)
% FSL's bet reads a NIfTI and reverses x of a neurologically stored one before bet2 runs, and back
% when it saves (fslio.c FslGetLeftRightOrder2; newimage read_volume's makeradiological()). The
% mesh is not symmetric, so this changes the mask; MEDI's mex, handed the array, never does it.
    if fsl_neurological(hdr)
        m = flip(BET(flip(img, 1), matrix_size, vox), 1);
    else
        m = BET(img, matrix_size, vox);
    end
end

function tf = fsl_neurological(hdr)
% FslGetLeftRightOrder2: the sform's determinant when sform_code > 0, else the qform's (whose
% rotation has determinant 1, so its sign is qfac's, pixdim(1), 0 read as 1), else radiological.
    h = hdr.hist;
    if h.sform_code > 0
        tf = det(double([h.srow_x(1:3); h.srow_y(1:3); h.srow_z(1:3)])) > 0;
    elseif h.qform_code > 0
        tf = hdr.dime.pixdim(1) >= 0;
    else
        tf = false;
    end
end

function nii = as_float(tmpl, a)
    nii = tmpl; nii.img = single(a);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.scl_slope = 1;  nii.hdr.dime.scl_inter = 0;
end

function nii = read_niigz(f)
    t = [tempname '.nii'];
    system(sprintf('gunzip -c ''%s'' > ''%s''', f, t));
    nii = load_untouch_nii(t);
    delete(t);
end

function write_niigz(nii, f)
    t = [tempname '.nii'];
    save_untouch_nii(nii, t);
    system(sprintf('gzip -c ''%s'' > ''%s''', t, f));
    delete(t);
end

function tb = toolbox_functions()
% Where the toolbox functions resolved: MEDI's BET, STI Suite's pcode and what it calls (QSM_star's
% iFDF and soft from Support_Functions), the Optimization Toolbox, Tim Ho's decompose_utils.
    tb = {'BET', 'bet2', 'MRPhaseUnwrap', 'V_SHARP', 'QSM_star', 'iFDF', 'soft', 'padarray', ...
          'lsqlin', 'lsqnonlin', ...
          'signalModel', 'objective1', 'objective2', 'objective3', 'pscModel', 'dscModel', ...
          'complex_to_real'};
end

function idir = intermediates_dir(out)
% QSMCI_INTERMEDIATES: a directory, or 1 for <out>/intermediates. Unset or 0: none.
    idir = getenv('QSMCI_INTERMEDIATES');
    if strcmp(idir, '0'), idir = ''; end
    if strcmp(idir, '1'), idir = fullfile(out, 'intermediates'); end
    if isempty(idir), return; end
    if ~startsWith(idir, filesep), idir = fullfile(pwd, idir); end
    if ~exist(idir, 'dir'), mkdir(idir); end
end

function write_intermediate(tmpl, a, f)
% One intermediate as float64 NIfTI, through the input's untouched header (affine preserved).
    a = double(a);
    tmpl.img = a;
    tmpl.hdr.dime.datatype = 64;  tmpl.hdr.dime.bitpix = 64;
    tmpl.hdr.dime.dim(1) = max(3, ndims(a));
    tmpl.hdr.dime.dim(2:5) = [size(a, 1) size(a, 2) size(a, 3) size(a, 4)];
    tmpl.hdr.dime.scl_slope = 1;  tmpl.hdr.dime.scl_inter = 0;
    write_niigz(tmpl, f);
end

function write_meta(idir, m)
% intermediates.json: M plus the MATLAB version, the thread count, and where each function in
% toolbox_functions() resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
