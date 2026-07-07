function writenii(fname, img, vox)
% Minimal NIfTI-1 writer (float32, .nii.gz). Self-contained MATLAB/Octave — no toolbox.
  img = single(img); dims = size(img);
  if numel(dims) < 3, dims(end+1:3) = 1; end
  gz = numel(fname) >= 3 && strcmp(fname(end-2:end), '.gz');
  if gz
    outdir = tempname(); mkdir(outdir);
    [~, base] = fileparts(fname);       % 'chimap.nii'
    niiname = fullfile(outdir, base);
  else
    niiname = fname;
  end
  fid = fopen(niiname, 'w', 'l');
  fwrite(fid, zeros(1, 352, 'uint8'), 'uint8');            % zero header + gap, then patch fields
  fseek(fid, 0,   'bof'); fwrite(fid, int32(348), 'int32');                 % sizeof_hdr
  fseek(fid, 40,  'bof'); fwrite(fid, int16([3 dims(1) dims(2) dims(3) 1 1 1 1]), 'int16');
  fseek(fid, 70,  'bof'); fwrite(fid, int16(16), 'int16'); fwrite(fid, int16(32), 'int16');
  fseek(fid, 76,  'bof'); fwrite(fid, single([1 vox(1) vox(2) vox(3) 0 0 0 0]), 'float32');
  fseek(fid, 108, 'bof'); fwrite(fid, single(352), 'float32');              % vox_offset
  fwrite(fid, single(1), 'float32'); fwrite(fid, single(0), 'float32');     % scl_slope, scl_inter
  fseek(fid, 252, 'bof'); fwrite(fid, int16(0), 'int16'); fwrite(fid, int16(1), 'int16'); % q/sform
  fseek(fid, 280, 'bof');
  fwrite(fid, single([vox(1) 0 0 0]), 'float32');          % srow_x
  fwrite(fid, single([0 vox(2) 0 0]), 'float32');          % srow_y
  fwrite(fid, single([0 0 vox(3) 0]), 'float32');          % srow_z
  fseek(fid, 344, 'bof'); fwrite(fid, uint8('n+1'), 'uint8'); fwrite(fid, uint8(0), 'uint8');
  fseek(fid, 352, 'bof'); fwrite(fid, img(:), 'float32');
  fclose(fid);
  if gz
    gzip(niiname);                        % -> niiname.gz in the writable temp dir
    movefile([niiname '.gz'], fname);     % place at the requested /output path
  end
end
