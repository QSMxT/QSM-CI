function recon(inp, out)
% QSM-CI `dipole` stage in MATLAB/Octave — thresholded k-space division.
% Reads <inp>/localfield.nii.gz (ppm) + mask + params.json, writes <out>/chimap.nii.gz (ppm).
  p   = jsondecode(fileread(fullfile(inp, 'params.json')));
  b0  = p.B0_dir(:)'; b0 = b0 / norm(b0);
  vox = p.voxel_size(:)';

  field = readnii(fullfile(inp, 'localfield.nii.gz'));
  mask  = readnii(fullfile(inp, 'mask.nii.gz')) > 0.5;

  sz = size(field);
  kfun = @(n, d) (mod((0:n-1) + floor(n/2), n) - floor(n/2)) / (n * d);
  [KX, KY, KZ] = ndgrid(kfun(sz(1),vox(1)), kfun(sz(2),vox(2)), kfun(sz(3),vox(3)));
  k2 = KX.^2 + KY.^2 + KZ.^2;
  kb = KX*b0(1) + KY*b0(2) + KZ*b0(3);
  D  = 1/3 - (kb.^2) ./ k2;
  D(1,1,1) = 0;

  thr = 0.2;
  Dt = D; s = abs(D) < thr; Dt(s) = sign(D(s)) * thr; Dt(Dt == 0) = thr;
  chi = real(ifftn(fftn(field) ./ Dt)) .* mask;

  writenii(fullfile(out, 'chimap.nii.gz'), single(chi), vox);
end
