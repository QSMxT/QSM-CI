function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB: HD-QSM, hybrid L1/L2 data fidelity (Lambert et al., MRM 2022),
% the authors' HDQSM.m (github.com/mglambert/HD-QSM, commit c456a94), run as its usage example
% runs it (HDQSM.m L27-34).
% Reads <inp>/localfield.nii.gz (ppm) + magnitude (echoes on the 4th axis) + mask + params.json,
% writes <out>/chimap.nii.gz (ppm).
%
% The usage example's inputs:
%   params.input  = mask .* local field in ppm (phase_use/phase_scale; the authors' challenge
%                   scripts also work in ppm);
%   params.weight = mask .* mag_use/max(mag_use), with mag_use the paper's echo combination
%                   sum(TE_i*mag_i^2)/sum(TE_i*mag_i) (Eq. 2);
%   params.kernel = the dipole kernel; HD-QSM ships none, and is "based on" FANSI, so it is FANSI's
%                   dipole_kernel_angulated(N, voxel_size, B0_dir) (FANSI-toolbox 93044a3);
%   params.mask   = the mask.
% HDQSM.m has no default for alphaL2 or mu1L2. The example uses 10^-4.785 and 10*alphaL2; the
% defaults here are QSM.rs's HdQsmParams (alphaL2 3e-5, mu1L2 100*alphaL2), because with the
% example's ratio of 10 HDQSM.m's ADMM diverges on in vivo scans at the alphaL2 that suits them
% (QSM.rs src/inversion/hdqsm.rs). Every other value is HDQSM.m's own: 20 L1 and 80 L2 iterations,
% tol_update 1e-2 (the code's value; its header says 1.0), mu1L1 = sqrt(mu1L2), alphaL1 =
% sqrt(alphaL2), mu2 1. chi is masked, as the other inversions leave it.
%
% Bundled: Jimmy Shen NIfTI toolbox, HDQSM.m and FANSI's dipole_kernel_angulated.m (plain .m). OS
% gunzip/gzip (no JVM). Optional <inp>/config.json overrides the parameters in `cfg` below.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, the data
% weight, the unmasked out.x and intermediates.json (the iteration counts, MATLAB version, thread
% count, where each function resolved). Unset, nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = double(p.voxel_size(:)');
    TE  = double(p.TE(:)');

    cfg = struct('alpha_l2', 3e-5, 'mu1_l2', [], 'max_iter_l1', 20, 'max_iter_l2', 80, ...
                 'tol_update', 1e-2);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end
    if isempty(cfg.mu1_l2), cfg.mu1_l2 = 100 * cfg.alpha_l2; end

    nlf   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(nlf.img);                                                % local field, ppm
    mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));   % echoes on dim 4
    nte   = size(mag, 4);
    if nte ~= numel(TE)
        error('recon:te', 'magnitude has %d echoes but params.json lists %d echo times', nte, numel(TE));
    end
    N = size(mask);

    te4 = reshape(TE, 1, 1, 1, nte);
    mag_use = sum(te4 .* mag.^2, 4) ./ sum(te4 .* mag, 4);                  % Eq. 2
    mag_use(~isfinite(mag_use)) = 0;

    prm = struct();
    prm.kernel = dipole_kernel_angulated(N, vox, b0);
    prm.weight = mask .* (mag_use / max(mag_use(:)));
    prm.input = mask .* field;
    prm.mask = mask;
    prm.alphaL2 = double(cfg.alpha_l2);
    prm.mu1L2 = double(cfg.mu1_l2);
    prm.maxOuterIterL1 = double(cfg.max_iter_l1);
    prm.maxOuterIterL2 = double(cfg.max_iter_l2);
    prm.tol_update = double(cfg.tol_update);
    res = HDQSM(prm);
    x = double(res.x);
    chi = x .* mask;

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nlf, prm.weight, fullfile(idir, 'weight.nii.gz'));
        write_intermediate(nlf, x, fullfile(idir, 'x_unmasked.nii.gz'));
        write_meta(idir, struct('cfg', cfg, 'iterL1', double(res.iterL1), 'iterL2', double(res.iterL2)));
    end

    nlf.img = single(chi);
    nlf.hdr.dime.datatype = 16;  nlf.hdr.dime.bitpix = 32;
    nlf.hdr.dime.dim(1) = 3;  nlf.hdr.dime.dim(5) = 1;
    nlf.hdr.dime.scl_slope = 1;  nlf.hdr.dime.scl_inter = 0;
    write_niigz(nlf, fullfile(out, 'chimap.nii.gz'));
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
    tb = {'HDQSM', 'dipole_kernel_angulated'};
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
% intermediates.json: M plus the MATLAB version, the thread count, and where each function resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
