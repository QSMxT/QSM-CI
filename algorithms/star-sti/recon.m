function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — STI Suite v3 STAR-QSM dipole inversion.
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
%
% Bundled: Jimmy Shen NIfTI toolbox, STI Suite v3 Core/Support functions (obfuscated .p),
% and a padarray shim (no Image Processing Toolbox). OS gunzip/gzip (no JVM). See BUILD.md.
% Optional <inp>/config.json overrides {padsize}.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    H   = p.B0_dir(:)'; H = H / norm(H);
    vox = p.voxel_size(:)';
    B0  = p.B0;                       % Tesla
    TE  = p.TE(1);                    % seconds (any TE works; the TE/B0 factor cancels)

    cfg = struct('padsize', 12);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end
    ps = double(cfg.padsize); padsize = [ps ps ps];

    nii   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(nii.img);                                        % local field, ppm
    Mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;

    % ppm local field -> tissue phase (radians at TE); STI Suite's QSM_star undoes the same
    % 2*pi*gamma*B0*TE scaling to recover chi in ppm, so the exact TE only sets the numeric scale.
    GYRO = 42.576e6;                                                % Hz/T
    TissuePhase = field * 1e-6 * 2*pi * GYRO * B0 * TE;

    % STI Suite's calcD2Matrix indexes assuming even matrix dims; pad odd dims to even
    % (post) before the inversion and crop back after (lossless zero-pad for the FFT model).
    sz0 = size(TissuePhase); po = mod(sz0, 2);
    TP  = padarray(TissuePhase, po, 0, 'post');
    Mk  = padarray(double(Mask), po, 0, 'post');
    chi = QSM_star(TP, Mk, 'TE', TE*1000, 'B0', B0, 'H', H, ...
                   'padsize', padsize, 'voxelsize', vox);          % ppm
    chi = chi(1:sz0(1), 1:sz0(2), 1:sz0(3));
    chi = double(chi) .* Mask;

    nii.img = single(chi);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3;  nii.hdr.dime.dim(5) = 1;
    write_niigz(nii, fullfile(out, 'chimap.nii.gz'));
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
