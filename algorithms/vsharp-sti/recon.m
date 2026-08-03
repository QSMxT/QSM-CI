function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB — STI Suite v3 V-SHARP background field removal.
% Reads <inp>/totalfield.nii.gz (ppm) + mask + params.json, writes <out>/localfield.nii.gz (ppm).
%
% V-SHARP is a linear SMV deconvolution and is scale-agnostic, so the ppm field is filtered
% directly (no phase conversion needed). Bundled NIfTI toolbox + STI Suite v3 (.p) + IPT shims;
% OS gunzip/gzip (no JVM). Optional <inp>/config.json overrides {smvsize}. See BUILD.md.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    vox = p.voxel_size(:)';

    cfg = struct('smvsize', 12);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nii   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(nii.img);                                        % total field, ppm
    Mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;

    [TissuePhase, NewMask] = V_SHARP(field, double(Mask), ...
                                     'voxelsize', vox, 'smvsize', double(cfg.smvsize));
    local = double(TissuePhase) .* double(NewMask);                 % local field, ppm

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
