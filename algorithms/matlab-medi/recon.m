function recon(inp, out)
% QSM-CI `bfr+dipole` stage in MATLAB — Morphology Enabled Dipole Inversion (MEDI).
% Reads <inp>/totalfield.nii.gz (ppm) + magnitude + mask + params.json, does PDF
% background-field removal then MEDI_L1 dipole inversion, writes <out>/chimap.nii.gz (ppm).
%
% Bundled: Jimmy Shen NIfTI toolbox (no Image Processing Toolbox), Cornell MEDI toolbox.
% OS gunzip/gzip (compiled binaries have no JVM). Optional <inp>/config.json overrides
% {lambda, smv_radius, merit, percentage, cg_tol}. See BUILD.md.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';
    B0T = p.B0;                       % field strength (Tesla)
    TE  = p.TE(:)';                   % echo time(s), seconds

    cfg = struct('lambda', 1000, 'smv_radius', 5, 'merit', 0, ...
                 'percentage', 0.9, 'cg_tol', 0.01);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    % --- inputs ---
    ntf   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(ntf.img);                                  % total field, ppm
    Mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;
    mag   = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    if ndims(mag) == 4, iMag = sqrt(sum(mag.^2, 4)); else, iMag = mag; end   % RSS over echoes

    matrix_size = size(Mask);
    GYRO = 42.576e6;                          % Hz/T
    CF   = GYRO * B0T;                        % centre frequency, Hz
    if numel(TE) > 1, delta_TE = TE(2) - TE(1); else, delta_TE = TE(1); end

    % ppm field -> radians accrued over delta_TE (self-consistent with MEDI's ppm output scaling)
    iFreq = field * 1e-6 * 2*pi * CF * delta_TE;

    % noise proxy: SD ~ 1/SNR ~ 1/magnitude, normalised to unit median inside the mask
    iMagN = iMag / max(iMag(Mask));
    N_std = 1 ./ (iMagN + eps);
    N_std = N_std / median(N_std(Mask));
    N_std = N_std .* Mask;

    % --- work in a writable temp dir (MEDI writes RDF.mat + ./results/) ---
    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));

    % PDF background-field removal: total field -> local field (RDF, radians)
    voxel_size = vox; B0_dir = b0;
    RDF = PDF(iFreq, N_std, Mask, matrix_size, voxel_size, B0_dir, cfg.cg_tol, 30);

    % parse_QSM_input (MEDI_L1) loads these exact variable names from RDF.mat:
    save('RDF.mat', 'iFreq', 'RDF', 'N_std', 'iMag', 'Mask', ...
         'matrix_size', 'voxel_size', 'delta_TE', 'CF', 'B0_dir');

    args = {'lambda', cfg.lambda, 'percentage', cfg.percentage};
    if cfg.smv_radius > 0, args = [args, {'smv', cfg.smv_radius}]; end
    if cfg.merit,          args = [args, {'merit'}]; end
    chi = MEDI_L1(args{:});                          % susceptibility, ppm
    chi = chi .* Mask;

    cd(old);
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
