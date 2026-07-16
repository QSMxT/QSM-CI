function recon(inp, out)
% QSM-CI `unwrap+bfr` stage in MATLAB — STI Suite v3 iHARPERELLA.
% Integrated phase unwrapping + background field removal on wrapped phase.
% Reads <inp>/phase.nii.gz (radians, wrapped, 3D or 4D multi-echo) + magnitude + mask + params,
% writes <out>/localfield.nii.gz (ppm).
%
% iHARPERELLA is a single-echo method (Li et al., NMR Biomed 2014;27:219, DOI 10.1002/nbm.3056):
% it unwraps + removes background from ONE wrapped 3D phase image. We use the first echo (as QSM.rs/
% QSMxT and STI Suite's STI_Templates.m do), then convert to a ppm field (phase/(2*pi*gamma*B0*TE1)).
% Bundled NIfTI + STI Suite v3 (.p) + support functions + IPT shims. OS gunzip/gzip (no JVM).
% Optional <inp>/config.json overrides {niter, padsize}. See BUILD.md.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    vox = p.voxel_size(:)';
    B0  = p.B0;
    TE  = p.TE(:)';                          % seconds

    cfg = struct('niter', 40, 'padsize', 12);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end
    ps = double(cfg.padsize); padsize = [ps ps ps]; niter = double(cfg.niter);

    nii   = read_niigz(fullfile(inp, 'phase.nii.gz'));
    phase = double(nii.img);
    Mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;
    if ndims(phase) == 3, phase = phase(:,:,:,1); end
    ne = size(phase, 4);
    if numel(TE) < ne, TE = TE(1) * (1:ne); end   % fall back to uniform spacing if TE underspecified

    GYRO = 42.576e6;                                             % Hz/T
    % STI Suite's SMVFiltering (inside iHARPERELLA) indexes with size/2, which is fractional on
    % odd dims (e.g. 205) -> "Integer operands required for colon operator" and a corrupted filter.
    % Pad odd dims to the next even size before the call and crop back after (the pad is outside
    % the mask). The pad MUST preserve the array/FFT center: iHARPERELLA's SMV/dipole kernels place
    % the frequency origin at floor(N/2)+1, so an even N moves that origin +1 voxel vs the odd N.
    % A one-sided 'post' pad leaves the data content on the old indices -> its true center no longer
    % coincides with the kernel origin (1-voxel misregistration on every SMV/dipole convolution) ->
    % geometry corrupted, correlation ~random. Adding the extra voxel on the FRONT ('pre') shifts
    % the content so its center maps to floor(Neven/2)+1 == the kernel origin; cropping the SAME
    % 'pre' offset back out restores alignment. Robust for any combination of odd dims.
    sz0 = size(Mask); po = mod(sz0, 2);          % +1 per axis that is odd, e.g. [1 0 1]
    % First echo only. iHARPERELLA processes a single wrapped phase image (see header). Feeding it
    % every echo and TE^2-weighting made the field near-random (corr ~0.10): late 7T echoes (20/28 ms)
    % are heavily wrapped, iHARPERELLA unwraps them worst, and TE^2 weights those failures ~49x the
    % first echo. QSM.rs uses echo 1 and scores well.
    pe = padarray(phase(:,:,:,1), po, 0, 'pre');
    Mk = padarray(double(Mask),   po, 0, 'pre');
    tp = iHARPERELLA(pe, Mk, 'voxelsize', vox, 'padsize', padsize, 'niter', niter);  % rad, local
    tp = tp(po(1)+1 : po(1)+sz0(1), po(2)+1 : po(2)+sz0(2), po(3)+1 : po(3)+sz0(3));
    local = (double(tp) / (2*pi * GYRO * B0 * TE(1)) * 1e6) .* Mask;                  % ppm

    nii.img = single(local);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3;  nii.hdr.dime.dim(5) = 1;
    write_niigz(nii, fullfile(out, 'localfield.nii.gz'));
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
