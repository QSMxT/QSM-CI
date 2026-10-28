function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — Morphology Enabled Dipole Inversion (MEDI).
% Reads <inp>/localfield.nii.gz (ppm) + magnitude (echoes on the 4th axis) + mask + params.json,
% runs MEDI_L1 on the local (tissue) field as MEDI's own pipeline (the toolbox's README.m) does,
% and writes <out>/chimap.nii.gz (ppm). No background-field removal: the pipeline's bfr stage
% provides the local field, where MEDI's README.m runs PDF.
%
% Bundled: Jimmy Shen NIfTI toolbox, Cornell MEDI toolbox 2024.11.26 (the release QSM.rs's MEDI
% port follows). OS gunzip/gzip (compiled binaries have no JVM). Optional <inp>/config.json
% overrides the parameters in `cfg` below. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64, what MEDI_L1
% reads from RDF.mat (RDF, N_std, iMag, Mask_CSF), the R2* map Mask_CSF comes from, the mask
% MEDI_L1 inverted on, and intermediates.json (MEDI_L1's arguments, MATLAB version, thread count).
% Unset (the default), nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';
    B0T = p.B0;                       % field strength (Tesla)
    TE  = p.TE(:)';                   % echo time(s), seconds

    % Every default is what MEDI_L1 (parse_QSM_input.m) does when the option isn't passed, which
    % is also what MEDI's README.m pipeline runs: MEDI_L1('lambda',1000,'lambda_CSF',100,'merit','smv',5).
    %   smv = 0 (or smv_radius = 0) passes 'nosmv'; merit = 0 passes 'nomerit'.
    %   csf: MEDI+0. MEDI_L1 adds the CSF term when RDF.mat holds Mask_CSF, which README.m makes
    %        with extract_CSF(arlo(TE, |echoes|), Mask, voxel_size); recon.m does the same.
    %   zeropad: MEDI_L1's 'zeropad' (voxels appended at the end of x, y, z; see below).
    cfg = struct('lambda', 1000, 'smv', 1, 'smv_radius', 5, 'smv_shrink_mask', 1, 'merit', 1, ...
                 'percentage', 0.9, 'data_weighting', 1, 'cg_max_iter', 100, 'cg_tol', 0.01, ...
                 'max_iter', 10, 'tol_norm_ratio', 0.1, 'csf', 1, 'lambda_csf', 100, ...
                 'csf_r2s_threshold', 5, 'csf_erode', 1, 'zeropad', 0);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    % --- inputs ---
    ntf   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(ntf.img);                                  % local (tissue) field, ppm
    Mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);   % 0/1, as BET's
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));   % echoes on dim 4
    nte   = size(mag, 4);
    if nte ~= numel(TE)
        error('recon:te', 'magnitude has %d echoes but params.json lists %d echo times', nte, numel(TE));
    end
    matrix_size = size(Mask);

    % README.m: iMag = sqrt(sum(abs(iField).^2,4)); [iFreq_raw, N_std] = Fit_ppm_complex(iField).
    % Fit_ppm_complex's N_std (dp1) depends only on the echo magnitudes, so the magnitudes give
    % exactly the N_std the complex echoes would.
    iMag = sqrt(sum(mag.^2, 4));
    [~, N_std] = Fit_ppm_complex(mag);

    % README.m's units: CF is the centre frequency, delta_TE the echo spacing TE(2) - TE(1), or TE
    % for one echo (Read_DICOM). MEDI_L1 works on the field in radians over delta_TE and converts
    % chi back to ppm with x/(2*pi*delta_TE*CF)*1e6.
    CF = 42.576e6 * B0T;                                      % Hz
    if nte > 1, delta_TE = TE(2) - TE(1); else, delta_TE = TE(1); end
    iFreq = field * 1e-6 * 2*pi * CF * delta_TE;              % ppm -> radians over delta_TE
    RDF = iFreq;           % the local field: MEDI_L1 inverts RDF (it reads iFreq without using it)
    voxel_size = vox; B0_dir = b0;

    % MEDI+0 (README.m): R2s = arlo(TE, abs(iField)); Mask_CSF = extract_CSF(R2s, Mask, voxel_size).
    % Only with three or more echoes: arlo gives no R2* for one echo, and 0 everywhere for two
    % (which would make every voxel of the central sphere "CSF"). extract_CSF errors when the
    % central sphere holds fewer than three low-R2* regions, and MEDI_L1 returns NaN for an empty
    % CSF mask; in those cases MEDI_L1 runs without the CSF term, as it does without Mask_CSF.
    R2s = []; Mask_CSF = [];
    if cfg.csf && nte >= 3
        R2s = arlo(TE, mag);
        try
            Mask_CSF = extract_CSF(R2s, Mask, voxel_size, cfg.csf_erode, cfg.csf_r2s_threshold);
        catch err
            fprintf('extract_CSF: %s; running without the CSF term\n', err.message);
            Mask_CSF = [];
        end
        if ~any(Mask_CSF(:)), Mask_CSF = []; end
    end

    % --- work in a writable temp dir (MEDI writes RDF.mat + ./results/) ---
    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));

    smv = cfg.smv && cfg.smv_radius > 0;
    pad = round(cfg.zeropad(:)') .* [1 1 1];
    % With SMV, sphere_kernel's grid -N/2:N/2-1 centres the sphere half a voxel off along an axis
    % with an odd number of voxels, and MEDI_L1 diverges there. So axes still odd after zeropad get
    % one more voxel (as QSM.rs does).
    if smv, pad = pad + mod(matrix_size + pad, 2); end
    % The padding is what MEDI_L1's 'zeropad' does (padarray(..., 'post') on what it reads from
    % RDF.mat, then crop), done here: in 2024.11.26 'zeropad' errors, because parse_QSM_input
    % leaves opts.matrix_size (reg_MEDI's epsilon) and opts.Mask/Mask_CSF (reg_CSF) unpadded.
    matrix_size0 = matrix_size;
    if any(pad)
        matrix_size = matrix_size0 + pad;
        iFreq = pad_post(iFreq, matrix_size);  RDF = pad_post(RDF, matrix_size);
        N_std = pad_post(N_std, matrix_size);  iMag = pad_post(iMag, matrix_size);
        Mask = pad_post(Mask, matrix_size);
        if ~isempty(Mask_CSF), Mask_CSF = pad_post(Mask_CSF, matrix_size); end
    end

    % parse_QSM_input (MEDI_L1) loads these exact variable names from RDF.mat:
    save('RDF.mat', 'iFreq', 'RDF', 'N_std', 'iMag', 'Mask', ...
         'matrix_size', 'voxel_size', 'delta_TE', 'CF', 'B0_dir');
    if ~isempty(Mask_CSF), save('RDF.mat', 'Mask_CSF', '-append'); end

    args = {'lambda', cfg.lambda, 'percentage', cfg.percentage, ...
            'data_weighting', cfg.data_weighting, 'cg_max_iter', cfg.cg_max_iter, ...
            'cg_tol', cfg.cg_tol, 'max_iter', cfg.max_iter, 'tol_norm_ratio', cfg.tol_norm_ratio};
    if smv
        args = [args, {'smv', cfg.smv_radius, 'smv_shrink_mask', cfg.smv_shrink_mask}];
    else
        args = [args, {'nosmv'}];
    end
    if cfg.merit, args = [args, {'merit'}]; else, args = [args, {'nomerit'}]; end
    if ~isempty(Mask_CSF), args = [args, {'lambda_CSF', cfg.lambda_csf}]; end
    [chi, ~, ~, resultsfile] = MEDI_L1(args{:});      % susceptibility, ppm
    % MEDI_L1 zeroes chi outside the mask it inverted on (with SMV, the eroded mask) and then
    % subtracts the CSF mean everywhere; keep chi zero outside that mask, as the other inversions do.
    Mask_inv = load(resultsfile, 'Mask');  Mask_inv = Mask_inv.Mask > 0;
    chi = chi .* Mask_inv;
    if any(pad)            % back to the input grid, as 'zeropad' crops to matrix_size0
        r = {1:matrix_size0(1), 1:matrix_size0(2), 1:matrix_size0(3)};
        chi = chi(r{:});  Mask_inv = Mask_inv(r{:});
        RDF = RDF(r{:});  N_std = N_std(r{:});  iMag = iMag(r{:});
        if ~isempty(Mask_CSF), Mask_CSF = Mask_CSF(r{:}); end
    end

    cd(old);
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(ntf, RDF, fullfile(idir, 'rdf.nii.gz'));
        write_intermediate(ntf, N_std, fullfile(idir, 'n_std.nii.gz'));
        write_intermediate(ntf, iMag, fullfile(idir, 'imag.nii.gz'));
        write_intermediate(ntf, Mask_inv, fullfile(idir, 'mask_inverted.nii.gz'));
        if ~isempty(R2s), write_intermediate(ntf, R2s, fullfile(idir, 'r2s.nii.gz')); end
        if ~isempty(Mask_CSF), write_intermediate(ntf, Mask_CSF, fullfile(idir, 'mask_csf.nii.gz')); end
        write_meta(idir, struct('medi_args', {cellfun(@num2str, args, 'UniformOutput', false)}));
    end
    ntf.img = single(chi);
    ntf.hdr.dime.datatype = 16;  ntf.hdr.dime.bitpix = 32;
    ntf.hdr.dime.dim(1) = 3;  ntf.hdr.dime.dim(5) = 1;
    write_niigz(ntf, fullfile(out, 'chimap.nii.gz'));
end

function b = pad_post(a, sz)
% Zeros appended at the end of each axis, as padarray(a, sz - size(a), 'post').
    b = zeros(sz, 'like', a);
    b(1:size(a, 1), 1:size(a, 2), 1:size(a, 3)) = a;
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
    tb = {'MEDI_L1', 'parse_QSM_input', 'gradient_mask', 'dataterm_mask', 'cgsolve', ...
          'Fit_ppm_complex', 'arlo', 'extract_CSF', 'reg_CSF', 'SMV', 'sphere_kernel'};
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
