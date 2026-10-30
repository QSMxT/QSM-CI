function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB: SHARP as SEPIA runs it, Tian Liu's SHARP.m (kschan0214/sepia
% db939cc, misc/background_removal/SHARP/SHARP.m) with the MEDI toolbox's SMV.m, SMV_kernel.m and
% sphere_kernel.m (MEDI 2024.11.26).
% Reads <inp>/totalfield.nii.gz (ppm) + mask + params.json, writes <out>/localfield.nii.gz (ppm).
%
% What SEPIA's BackgroundRemovalMacro.m does with the settings its GUI exports for SHARP
% (refine 'None', no extra erosion; checked in licensed MATLAB, fidelity/REPORT.md):
% zeropad_odd_dimension(…, 'pre') pads each odd axis by one slice at its end, Wrapper_BFR_SHARP.m
% calls SHARP(totalField, mask, matrixSize, voxelSize, radius, threshold), and the padding is
% cropped off. The defaults are SEPIA's GUI's, radius 4 and threshold 0.03. The GUI labels the
% radius "voxel", but SHARP.m passes it to MEDI's sphere_kernel.m, which takes mm.
% SEPIA's own wrappers (sepia_addpath, sepia_universal_variables) only set the MATLAB path, which
% the compiled binary doesn't need, so recon calls the two SEPIA functions directly.
%
% SHARP is linear and scale-agnostic, so the ppm field is filtered directly. Bundled: Jimmy Shen
% NIfTI toolbox, SEPIA's SHARP.m and zeropad_odd_dimension.m, the MEDI functions above, and the
% real Image Processing Toolbox's padarray (compiled from licensed MATLAB; the MATLAB Runtime
% includes its runtime components). OS gunzip/gzip (no JVM). Optional <inp>/config.json
% overrides {radius, threshold}. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes SHARP.m's eroded mask
% (SMV(Mask, ..., radius) > 0.999, the expression SHARP.m uses, recomputed on the padded grid), the
% local field in float64, and intermediates.json (MATLAB version, thread count, and where each
% toolbox function resolved). Unset (the default), nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    vox = double(p.voxel_size(:)');

    cfg = struct('radius', 4, 'threshold', 0.03);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nii   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(nii.img);                                        % total field, ppm
    mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);
    n     = size(field);

    % BackgroundRemovalMacro.m: pad odd dimensions, SHARP via Wrapper_BFR_SHARP.m, crop
    fieldp = double(zeropad_odd_dimension(field, 'pre'));
    maskp  = double(zeropad_odd_dimension(mask, 'pre'));
    RDF    = SHARP(fieldp, maskp, size(fieldp), vox, double(cfg.radius), double(cfg.threshold));
    local  = double(zeropad_odd_dimension(RDF, 'post', n));        % local field, ppm

    idir = intermediates_dir(out);
    if ~isempty(idir)
        me = SMV(maskp, size(maskp), vox, double(cfg.radius)) > 0.999;
        write_intermediate(nii, zeropad_odd_dimension(double(me), 'post', n), fullfile(idir, 'sharp_mask.nii.gz'));
        write_intermediate(nii, local, fullfile(idir, 'localfield_f64.nii.gz'));
        write_meta(idir, struct('radius', cfg.radius, 'threshold', cfg.threshold, 'isreal', isreal(RDF)));
    end

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

function tb = toolbox_functions()
    tb = {'SHARP', 'zeropad_odd_dimension', 'SMV', 'SMV_kernel', 'sphere_kernel', 'padarray'};
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
% intermediates.json: M plus the MATLAB version, the thread count, and where each function of
% SEPIA, MEDI and the toolboxes resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
