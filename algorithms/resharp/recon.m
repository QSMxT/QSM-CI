function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB: RESHARP (Sun & Wilman, MRM 2014), the first author's resharp.m
% (github.com/sunhongfu/QSM, commit c75b138, background_field_removal/resharp.m, which QSM.rs's port
% cites), with its own defaults: a 3 mm kernel (round(r/vox) per axis, at least 2 voxels),
% Tikhonov lambda 1e-4, MATLAB cgs at tolerance 1e-6 for at most 200 iterations.
% Reads <inp>/totalfield.nii.gz (ppm) + mask + params.json, writes <out>/localfield.nii.gz (ppm),
% 0 outside RESHARP's eroded mask.
%
% RESHARP solves (H'H + lambda) x = H'H y, which is linear in the field with a relative CGS
% tolerance, so the ppm field is filtered directly (Hongfu Sun's drivers also pass ppm).
%
% Bundled: Jimmy Shen NIfTI toolbox, resharp.m, and the Image Processing Toolbox's padarray (compiled
% from licensed MATLAB; the Runtime includes its runtime components). OS gunzip/gzip (no JVM).
% Optional <inp>/config.json overrides {radius, lambda, iterations}. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes RESHARP's eroded mask, the
% local field in float64, and intermediates.json (the residual and regularisation norms, MATLAB
% version, thread count, where each function resolved). Unset, nothing changes.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    vox = double(p.voxel_size(:)');

    cfg = struct('radius', 3, 'lambda', 1e-4, 'iterations', 200);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nii   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(nii.img);                                                % total field, ppm
    mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);

    [lfs, mask_ero, res_term, reg_term] = resharp(field, mask, vox, double(cfg.radius), ...
                                                  double(cfg.lambda), double(cfg.iterations));

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nii, mask_ero, fullfile(idir, 'resharp_mask.nii.gz'));
        write_intermediate(nii, lfs, fullfile(idir, 'localfield_f64.nii.gz'));
        write_meta(idir, struct('radius', cfg.radius, 'lambda', cfg.lambda, 'iterations', cfg.iterations, ...
            'res_term', res_term, 'reg_term', reg_term));
    end

    nii.img = single(lfs);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3;  nii.hdr.dime.dim(5) = 1;
    nii.hdr.dime.scl_slope = 1;  nii.hdr.dime.scl_inter = 0;
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
    tb = {'resharp', 'padarray', 'cgs'};
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
% intermediates.json: M plus the MATLAB version, the thread count, and where each function resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
