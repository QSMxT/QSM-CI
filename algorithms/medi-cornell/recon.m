function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — Morphology Enabled Dipole Inversion (MEDI).
% Reads <inp>/localfield.nii.gz (ppm) + magnitude + mask + params.json and runs MEDI_L1
% dipole inversion directly on the local (tissue) field, writes <out>/chimap.nii.gz (ppm).
% (No background-field removal: the local field is provided by the pipeline's bfr stage. The
% Cornell PDF step used by the old bfr+dipole variant is gone; this is a pure dipole inversion.)
%
% Bundled: Jimmy Shen NIfTI toolbox, Cornell MEDI toolbox 2024.11.26 (the release QSM.rs's MEDI
% port follows). OS gunzip/gzip (compiled binaries have no JVM). Optional <inp>/config.json
% overrides {lambda, smv_radius, merit, percentage}. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, what MEDI_L1
% reads from RDF.mat (RDF, N_std, iMag) and intermediates.json (MATLAB version, thread count).
% Unset (the default), nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';
    B0T = p.B0;                       % field strength (Tesla)
    TE  = p.TE(:)';                   % echo time(s), seconds

    % lambda=1000: Cornell's default (MEDI_L1's parse_QSM_input). The field is put on a fixed
    % reference scale below, so the same lambda holds at any field strength.
    % smv_radius default 0: the input is already a local field (bfr done upstream), so MEDI's own
    % SMV background-suppression is off by default — this is a pure dipole inversion. Still tunable.
    % merit default 0 (model-error reweighting off). MEDI 2024.11.26 turns SMV and merit ON unless
    % told 'nosmv' / 'nomerit', so both are passed explicitly.
    cfg = struct('lambda', 1000, 'smv_radius', 0, 'merit', 0, 'percentage', 0.9);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    % --- inputs ---
    ntf   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(ntf.img);                                  % local (tissue) field, ppm
    Mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    if ndims(mag) == 4, iMag = sqrt(sum(mag.^2, 4)); else, iMag = mag; end   % RSS over echoes

    matrix_size = size(Mask);
    GYRO = 42.576e6;                          % Hz/T
    % MEDI is nonlinear and scale-dependent: its Gauss-Newton `lambda` must match the radian scale
    % of the data, or the iteration diverges (observed at 7T with a 3T-tuned lambda). The field is
    % already ppm (B0-normalised), so represent it internally at a FIXED reference scale (3T, 8 ms)
    % regardless of the actual B0/TE. The SAME factor is used for MEDI_L1's ppm output conversion,
    % so it cancels: chi stays in ppm while lambda=1000 stays tuned at any field strength.
    CF       = GYRO * 3.0;                     % reference centre frequency (3T), Hz
    delta_TE = 0.008;                          % reference echo spacing, s
    iFreq    = field * 1e-6 * 2*pi * CF * delta_TE;   % ppm field -> reference-scale radians

    % noise proxy: SD ~ 1/SNR ~ 1/magnitude, normalised to unit median inside the mask
    iMagN = iMag / max(iMag(Mask));
    N_std = 1 ./ (iMagN + eps);
    N_std = N_std / median(N_std(Mask));
    N_std = N_std .* Mask;

    % --- work in a writable temp dir (MEDI writes RDF.mat + ./results/) ---
    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));

    % No background removal: the input is already the local (tissue) field, so RDF is iFreq directly
    % (MEDI_L1 expects RDF = local field in radians). The old bfr+dipole variant ran PDF here.
    voxel_size = vox; B0_dir = b0;
    RDF = iFreq;

    % parse_QSM_input (MEDI_L1) loads these exact variable names from RDF.mat:
    save('RDF.mat', 'iFreq', 'RDF', 'N_std', 'iMag', 'Mask', ...
         'matrix_size', 'voxel_size', 'delta_TE', 'CF', 'B0_dir');

    args = {'lambda', cfg.lambda, 'percentage', cfg.percentage};
    if cfg.smv_radius > 0, args = [args, {'smv', cfg.smv_radius}]; else, args = [args, {'nosmv'}]; end
    if cfg.merit,          args = [args, {'merit'}];               else, args = [args, {'nomerit'}]; end
    chi = MEDI_L1(args{:});                          % susceptibility, ppm
    chi = chi .* Mask;

    cd(old);
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(ntf, RDF, fullfile(idir, 'rdf.nii.gz'));
        write_intermediate(ntf, N_std, fullfile(idir, 'n_std.nii.gz'));
        write_intermediate(ntf, iMag, fullfile(idir, 'imag.nii.gz'));
        write_meta(idir, struct('medi_args', {cellfun(@num2str, args, 'UniformOutput', false)}));
    end
    ntf.img = single(chi);
    ntf.hdr.dime.datatype = 16;  ntf.hdr.dime.bitpix = 32;
    ntf.hdr.dime.dim(1) = 3;  ntf.hdr.dime.dim(5) = 1;
    write_niigz(ntf, fullfile(out, 'chimap.nii.gz'));
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
% No pcode here: mcc traces every call. These record where the MEDI functions resolved.
    tb = {'MEDI_L1', 'parse_QSM_input', 'gradient_mask', 'dataterm_mask', 'cgsolve'};
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
