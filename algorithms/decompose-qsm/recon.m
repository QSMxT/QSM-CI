function recon(inp, out)
% QSM-CI `chi-separation` stage — DECOMPOSE-QSM (Tim Ho's open MATLAB implementation, GPL-3.0,
% github.com/timwahoo/DECOMPOSE-QSM), a signal-domain source-separation method.
%
% DECOMPOSE fits the multi-echo COMPLEX GRE signal per voxel to split χ into paramagnetic (χ+) and
% diamagnetic (χ−) sources: a 3-stage alternating non-linear least-squares fit (lsqcurvefit) of
% {C+, C−, C0, R2*_0, χ+, χ−}, then reconstructs χ+/χ− from the fitted params.
%
% INPUT: DECOMPOSE is defined on a QSM of each echo, χ(t) (Chen 2021, Eq. 4: "it is necessary to use
% TE-dependent QSM as the input"). The reference computes it per echo with STI Suite (Laplacian unwrap →
% V-SHARP → STAR-QSM) and builds y_data from QSM_multi(:,:,:,i). Here the per-echo QSM is the phantom's
% chimap-echoes.nii.gz (4D, one χ per echo, echo order of the magnitude), and y_data is built from it exactly
% as DECOMPOSE_analysis.m does. A phantom without it falls back to chimap.nii.gz (χ_total) for every echo,
% with a note: that runs, but without the echo dependence the method separates on. The per-voxel fit is the
% reference code.
%
% Consumes multi-echo magnitude + per-echo QSM (chimap-echoes; else χ_total, chimap) + mask + params; writes
% chi-para.nii.gz (χ+) and chi-dia.nii.gz (χ−, positive magnitude). Needs the Optimization Toolbox (lsqcurvefit). The per-voxel
% fit is SLOW; $DECOMPOSE_CROPBOX (central-box side, voxels) limits it for a feasibility/speed run and
% $DECOMPOSE_NINNER overrides the inner-iteration count (default 10).
    addpath_env('DECOMPOSE_UTILS', true);       % {psc,dsc,signal}Model, objective{1,2,3}, complex_to_real
    addpath_env('CHISEP_NIFTI', false);         % Jimmy Shen NIfTI I/O

    p = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0 = p.B0; TE = p.TE(:)';                    % B0 (T), echo times (s)
    gamma = 42.58 * 2*pi;                        % rad/T (as in the DECOMPOSE reference)

    rd = @(f) double(getfield(read_niigz(fullfile(inp, f)), 'img'));
    mag_multi_echo = rd('magnitude.nii.gz');    % [X Y Z TE]
    mn = read_niigz(fullfile(inp, 'mask.nii.gz')); mask_brain = double(mn.img) > 0.5;
    mag_multi_echo = mag_multi_echo / max(mag_multi_echo(:));
    [N1, N2, N3, ~] = size(mag_multi_echo);

    % --- QSM of each echo, χ(t) (ppm), [X Y Z TE] ---
    if isfile(fullfile(inp, 'chimap-echoes.nii.gz'))
        QSM_multi = rd('chimap-echoes.nii.gz');
        if size(QSM_multi, 4) ~= numel(TE)
            error('chimap-echoes.nii.gz has %d echoes but params.json lists %d', size(QSM_multi, 4), numel(TE));
        end
        fprintf('DECOMPOSE: per-echo QSM (chimap-echoes.nii.gz)\n');
    else
        fprintf('DECOMPOSE: NOTE no chimap-echoes.nii.gz; using chimap.nii.gz (chi_total) for every echo\n');
        QSM_multi = repmat(rd('chimap.nii.gz'), [1 1 1 numel(TE)]);
    end

    % --- complex signal per echo (Eq. 4), built as DECOMPOSE_analysis.m builds y_data ---
    y_data = zeros(N1, N2, N3, numel(TE));
    for i = 1:numel(TE)
        mag = mag_multi_echo(:,:,:,i);
        y_data(:,:,:,i) = (mag.*exp(-1i*(2/3).*squeeze(QSM_multi(:,:,:,i))*gamma*B0*TE(i))).*mask_brain;
    end

    % --- which voxels to fit (optional central-box crop for a feasibility/speed run) ---
    fitmask = mask_brain;
    box = str2double(getenv('DECOMPOSE_CROPBOX'));
    if ~isnan(box) && box > 0
        sel = false(N1, N2, N3); c = round([N1 N2 N3]/2); h = floor(box/2);
        sel(max(1,c(1)-h):min(N1,c(1)+h), max(1,c(2)-h):min(N2,c(2)+h), max(1,c(3)-h):min(N3,c(3)+h)) = true;
        fitmask = fitmask & sel;
    end
    N_inner = 10; niv = str2double(getenv('DECOMPOSE_NINNER')); if ~isnan(niv) && niv > 0; N_inner = niv; end
    fprintf('DECOMPOSE: fitting %d voxels (N_inner=%d)\n', nnz(fitmask), N_inner);

    % Start a local parallel pool so the per-voxel parfor runs across all cores. Compiled WITH the
    % Parallel Computing Toolbox, the MATLAB Runtime can open a pool up to the container's core count
    % without a license; degrade gracefully to a serial parfor if the pool can't start. $DECOMPOSE_WORKERS
    % caps the worker count (e.g. when a runner shares cores between concurrent jobs).
    try
        if isempty(gcp('nocreate'))
            nw = str2double(getenv('DECOMPOSE_WORKERS'));
            if isnan(nw) || nw < 1; nw = feature('numcores'); end
            c = parcluster('local');
            jsl = tempname; mkdir(jsl); c.JobStorageLocation = jsl;   % writable scratch (container HOME may be read-only)
            c.NumWorkers = nw;
            parpool(c, nw);
        end
        fprintf('DECOMPOSE: parpool with %d workers\n', gcp().NumWorkers);
    catch e
        fprintf('DECOMPOSE: no parpool (%s) — running serial\n', e.message);
    end

    opt = optimoptions('lsqcurvefit', 'Display', 'off', 'UseParallel', false);
    lb = [0 0 0]; ub = [inf inf inf]; lb2 = 0; ub2 = inf; upper = 0.5; lb3 = [0 -upper]; ub3 = [upper 0];
    Cp = zeros(N1,N2,N3); Cm = zeros(N1,N2,N3); C0m = zeros(N1,N2,N3);
    R0m = zeros(N1,N2,N3); chp = zeros(N1,N2,N3); chm = zeros(N1,N2,N3);
    t0 = tic;
    parfor i = 1:N1
        for j = 1:N2
            for k = 1:N3
                if ~fitmask(i,j,k); continue; end
                ydata = squeeze(y_data(i,j,k,:))';
                if sum(ydata) == 0; continue; end
                chi_0 = [0.05 -0.05]; R0 = 25; C0 = [0.3 0.3 0.4];
                for it = 1:N_inner
                    m1 = @(x,xd) complex_to_real(objective1(x, xd, chi_0(1), chi_0(2), R0, B0));
                    C0 = lsqcurvefit(m1, C0, TE, complex_to_real(ydata), lb, ub, opt);
                    m2 = @(x,xd) complex_to_real(objective2(x, xd, C0(1), C0(2), C0(3), chi_0(1), chi_0(2), B0));
                    R0 = lsqcurvefit(m2, R0, TE, complex_to_real(log(ydata)), lb2, ub2, opt);
                    m3 = @(x,xd) complex_to_real(objective3(x, xd, C0(1), C0(2), C0(3), R0, B0));
                    chi_0 = lsqcurvefit(m3, chi_0, TE, complex_to_real(log(ydata)), lb3, ub3, opt);
                end
                Cp(i,j,k)=C0(1); Cm(i,j,k)=C0(2); C0m(i,j,k)=C0(3);
                R0m(i,j,k)=R0; chp(i,j,k)=chi_0(1); chm(i,j,k)=chi_0(2);
            end
        end
        if any(fitmask(i,:,:), 'all'); fprintf('slice %d done (%.0fs elapsed)\n', i, toc(t0)); end
    end
    fprintf('DECOMPOSE: fit done in %.0f s\n', toc(t0));

    % --- reconstruct χ+ (paramagnetic) and χ− (diamagnetic) from the fitted parameters ---
    den = (2/3) * gamma * B0 * sum(TE);
    PSC = zeros(N1,N2,N3); DSC = zeros(N1,N2,N3);
    for i = 1:N1
        for j = 1:N2
            for k = 1:N3
                if ~fitmask(i,j,k); continue; end
                cp = pscModel(TE, Cp(i,j,k), Cm(i,j,k), C0m(i,j,k), chp(i,j,k), chm(i,j,k), R0m(i,j,k), B0);
                cn = dscModel(TE, Cp(i,j,k), Cm(i,j,k), C0m(i,j,k), chp(i,j,k), chm(i,j,k), R0m(i,j,k), B0);
                PSC(i,j,k) = -sum(angle(cp))/den;    % PCS → χ+
                DSC(i,j,k) = -sum(angle(cn))/den;    % DCS → χ−
            end
        end
    end
    % Output mapping, as the paper defines it: the paramagnetic component is the PCS, reconstructed from the
    % paramagnetic-pool sub-model (pscModel, Eq. 6), and the diamagnetic component is the DCS (dscModel, Eq. 7).
    % The reference demo writes DSC to the file 'XPSC' and PSC to 'XDSC' — a filename swap, not followed here.
    write_niigz(setimg(mn, single(abs(PSC) .* fitmask)), fullfile(out, 'chi-para.nii.gz'));  % χ+ = |PCS|
    write_niigz(setimg(mn, single(abs(DSC) .* fitmask)), fullfile(out, 'chi-dia.nii.gz'));   % |χ−| = |DCS|
end
function addpath_env(name, recurse)
    d = getenv(name);
    if ~isempty(d); if recurse; addpath(genpath(d)); else; addpath(d); end; end
end
function nii = setimg(tmpl, img)
    nii = tmpl; nii.img = img;
    nii.hdr.dime.datatype = 16; nii.hdr.dime.bitpix = 32; nii.hdr.dime.dim(1) = 3; nii.hdr.dime.dim(5) = 1;
end
function nii = read_niigz(f)
    t = [tempname '.nii']; system(sprintf('gunzip -c ''%s'' > ''%s''', f, t)); nii = load_untouch_nii(t); delete(t);
end
function write_niigz(nii, f)
    t = [tempname '.nii']; save_untouch_nii(nii, t); system(sprintf('gzip -c ''%s'' > ''%s''', t, f)); delete(t);
end
