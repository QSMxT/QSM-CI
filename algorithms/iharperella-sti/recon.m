function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB: STI Suite 3.0's iHARPERELLA (Li et al., NMR Biomed 2014), the
% authors' function (Core_Functions_P/iHARPERELLA.p) with its own defaults (niter 40, padsize 0).
% Reads <inp>/totalfield.nii.gz (ppm) + mask + params.json, writes <out>/localfield.nii.gz (ppm),
% 0 outside the mask.
%
% STI's help text calls iHARPERELLA on the "raw phase", but probed in licensed MATLAB it does not
% unwrap (QSM.rs src/bgremove/iharperella.rs): it takes the spectral Laplacian of its input as it
% is. So it is given the unwrapped total field, as QSM.rs's port is. Its Laplacian and LSQR solve
% are linear with a relative tolerance, so the ppm field is used directly. Defaults probed:
% niter 40; padsize 0 (bitwise equal to [0 0 0]; STI_Templates.m lists [12 12 12]).
%
% Bundled: Jimmy Shen NIfTI toolbox, STI Suite 3.0 Core_Functions_P (pcode), and the real Image
% Processing Toolbox functions its pcode calls (compiled from licensed MATLAB; the Runtime includes
% their runtime components). OS gunzip/gzip (no JVM). Optional <inp>/config.json overrides
% {niter, padsize}. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes iHARPERELLA's unmasked
% output (float64) and intermediates.json (MATLAB version, thread count, and where each toolbox
% function resolved). Unset (the default), nothing changes.

% Toolbox functions STI Suite's pcode calls, which mcc can't trace into: name them so they are
% bundled. Found by profiling a licensed run (../../fidelity/matlab/README.md, `trace`); keep
% toolbox_functions() below in step.
%#function padarray

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    vox = double(p.voxel_size(:)');

    cfg = struct('niter', 40, 'padsize', 0);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nii   = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    field = double(nii.img);                                        % total field, ppm
    Mask  = double(double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5);

    args = {'voxelsize', vox, 'niter', double(cfg.niter)};
    if any(double(cfg.padsize(:)))                                  % 0: the function's default
        args = [args, {'padsize', double(cfg.padsize(:)') .* [1 1 1]}];
    end
    TissuePhase = double(iHARPERELLA(field, Mask, args{:}));
    local = TissuePhase .* Mask;                                    % local field, ppm

    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(nii, TissuePhase, fullfile(idir, 'iharperella_unmasked.nii.gz'));
        write_meta(idir, struct('niter', cfg.niter, 'padsize', cfg.padsize));
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
    % load_untouch_nii returns the stored values: apply scl_slope/scl_inter where set.
    s = double(nii.hdr.dime.scl_slope); o = double(nii.hdr.dime.scl_inter);
    if s ~= 0 && ~(s == 1 && o == 0)
        nii.img = double(nii.img) * s + o;
        nii.hdr.dime.scl_slope = 1;  nii.hdr.dime.scl_inter = 0;
    end
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
