function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB — thresholded k-space division.
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
% Bundled NIfTI toolbox (no Image Processing Toolbox); OS gunzip/gzip (no JVM). See BUILD.md.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
    vox = p.voxel_size(:)';

    nii   = read_niigz(fullfile(inp, 'localfield.nii.gz'));
    field = double(nii.img);
    mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;

    sz = size(field);
    kfun = @(n, d) (mod((0:n-1) + floor(n/2), n) - floor(n/2)) / (n * d);
    [KX, KY, KZ] = ndgrid(kfun(sz(1),vox(1)), kfun(sz(2),vox(2)), kfun(sz(3),vox(3)));
    k2 = KX.^2 + KY.^2 + KZ.^2;
    kb = KX*b0(1) + KY*b0(2) + KZ*b0(3);
    D  = 1/3 - (kb.^2) ./ k2;  D(1,1,1) = 0;

    thr = 0.2;  Dt = D;
    small = abs(D) < thr;  Dt(small) = sign(D(small)) * thr;  Dt(Dt == 0) = thr;

    chi = real(ifftn(fftn(field) ./ Dt)) .* mask;

    nii.img = single(chi);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
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
