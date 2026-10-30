function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB — STI Suite v3 V-SHARP background field removal.
% Reads <inp>/totalfield.nii.gz (ppm) + mask + params.json, writes <out>/localfield.nii.gz (ppm).
%
% V-SHARP is a linear SMV deconvolution and is scale-agnostic, so the ppm field is filtered
% directly (no phase conversion needed). Bundled: Jimmy Shen NIfTI toolbox, STI Suite v3
% Core_Functions_P (pcode), and the real Image Processing Toolbox functions STI Suite calls
% (compiled from licensed MATLAB; the MATLAB Runtime includes their runtime components). OS
% gunzip/gzip (no JVM). Optional <inp>/config.json overrides {smvsize}. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes V_SHARP's eroded mask and
% its unmasked output (float64), and intermediates.json (MATLAB version, thread count, and where each
% toolbox function resolved). Unset (the default), nothing changes.

% Toolbox functions STI Suite's pcode calls, which mcc can't trace into: name them so they are
% bundled. Found by profiling a licensed run (../../fidelity/matlab/README.md, `trace`); keep
% toolbox_functions() below in step.
%#function padarray

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

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nii, NewMask, fullfile(idir, 'newmask.nii.gz'));
        write_intermediate(nii, TissuePhase, fullfile(idir, 'vsharp_unmasked.nii.gz'));
        write_meta(idir, struct());
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
    tb = {'padarray'};
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
% intermediates.json: M plus the MATLAB version, the thread count, and where each toolbox
% function in the %#function pragma resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
