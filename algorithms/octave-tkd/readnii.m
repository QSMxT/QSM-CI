function [img, info] = readnii(fname)
% Minimal NIfTI-1 reader (handles .nii and .nii.gz). Self-contained MATLAB/Octave — no toolbox.
  fn = fname;
  if numel(fname) >= 3 && strcmp(fname(end-2:end), '.gz')
    outdir = tempname(); mkdir(outdir);
    [~, base] = fileparts(fname);          % base = e.g. 'localfield.nii'
    gztmp = fullfile(outdir, [base '.gz']);
    copyfile(fname, gztmp);                % /input is read-only; unzip a writable copy
    gunzip(gztmp);                         % -> outdir/localfield.nii
    fn = fullfile(outdir, base);
  end
  fid = fopen(fn, 'r', 'l');
  fseek(fid, 40,  'bof'); dim        = fread(fid, 8, 'int16');
  fseek(fid, 70,  'bof'); datatype   = fread(fid, 1, 'int16');
  fseek(fid, 76,  'bof'); pixdim     = fread(fid, 8, 'float32');
  fseek(fid, 108, 'bof'); vox_offset = fread(fid, 1, 'float32');
  scl_slope = fread(fid, 1, 'float32'); scl_inter = fread(fid, 1, 'float32');
  ndim = dim(1); dims = dim(2:1+ndim)';
  switch datatype
    case 2,   prec = 'uint8';   case 4,  prec = 'int16';   case 8,  prec = 'int32';
    case 16,  prec = 'float32'; case 64, prec = 'float64'; case 256, prec = 'int8';
    case 512, prec = 'uint16';  case 768, prec = 'uint32';
    otherwise, error('readnii: unsupported datatype %d', datatype);
  end
  fseek(fid, vox_offset, 'bof');
  data = fread(fid, prod(dims), [prec '=>double']);
  fclose(fid);
  if scl_slope ~= 0
    data = data * scl_slope + scl_inter;
  end
  img = reshape(data, dims);
  info = struct('dims', dims, 'pixdim', pixdim(2:1+ndim)');
end
