function recon(inp, out)
% QSM-CI `field-mapping` stage in MATLAB: STI Suite 3.0's Laplacian phase unwrapping,
% MRPhaseUnwrap (Core_Functions_P/MRPhaseUnwrap.p; Schofield & Zhu 2003, Li et al. 2011), and the
% echo combination STI Suite's QSM_GUI applies to its output.
% Reads <inp>/phase.nii.gz (radians, echoes on the 4th axis) + params.json, writes
% <out>/totalfield.nii.gz (ppm). The mask is not used.
%
% What QSM_GUI does ("3D GRE data", probed headless in licensed MATLAB; QSM.rs
% src/unwrap/laplacian.rs): MRPhaseUnwrap(phase, 'voxelsize', vs) once on all echoes, on the raw,
% unmasked wrapped phase, with its default padsize 12; then the unwrapped echoes are summed and the
% sum is used with TE = sum(TE). So the field is sum(phi_e) / sum(TE_e) in rad/s, converted to ppm
% with 42.576 MHz/T (the QSM-CI contract's gamma). Odd axes are zero-padded to even for
% MRPhaseUnwrap and cropped back (see below).
%
% Bundled: Jimmy Shen NIfTI toolbox, STI Suite 3.0 Core_Functions_P (pcode), and the real Image
% Processing Toolbox functions its pcode calls (compiled from licensed MATLAB; the Runtime includes
% their runtime components). OS gunzip/gzip (no JVM). Optional <inp>/config.json overrides
% {padsize}. See BUILD.md.
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes MRPhaseUnwrap's unwrapped
% echoes and its Laplacian (float64), the field in float64, and intermediates.json (MATLAB version,
% thread count, and where each toolbox function resolved). Unset (the default), nothing changes.

% Toolbox functions STI Suite's pcode calls, which mcc can't trace into: name them so they are
% bundled. Found by profiling a licensed run (../../fidelity/matlab/README.md, `trace`); keep
% toolbox_functions() below in step.
%#function padarray

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    vox = double(p.voxel_size(:)');
    TE  = double(p.TE(:)');

    cfg = struct('padsize', 12);
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end

    nph = read_niigz(fullfile(inp, 'phase.nii.gz'));
    ph  = double(nph.img);                                          % wrapped phase, rad
    if size(ph, 4) ~= numel(TE)
        error('recon:te', 'phase has %d echoes but params.json lists %d echo times', size(ph, 4), numel(TE));
    end

    args = {'voxelsize', vox};
    if double(cfg.padsize(1)) ~= 12 || numel(cfg.padsize) > 1        % 12: the function's default
        args = [args, {'padsize', double(cfg.padsize(:)') .* [1 1 1]}];
    end
    % MRPhaseUnwrap needs an even grid: probed in licensed R2023b, it errors ("Index in position 1/2
    % is invalid") on an odd x or y extent and returns one slice too many on an odd z. So odd axes
    % get one zero slice at the end, as qsmart-matlab's recon.m pads for STI Suite, and the result
    % is cropped back. Even grids are untouched.
    sz0 = [size(ph, 1) size(ph, 2) size(ph, 3)];
    po = mod(sz0, 2);
    php = zeros([sz0 + po, size(ph, 4)]);
    php(1:sz0(1), 1:sz0(2), 1:sz0(3), :) = ph;
    [Unwrapped, Laplacian] = MRPhaseUnwrap(php, args{:});
    Unwrapped = double(Unwrapped(1:sz0(1), 1:sz0(2), 1:sz0(3), :));
    Laplacian = Laplacian(1:sz0(1), 1:sz0(2), 1:sz0(3), :);
    field = sum(Unwrapped, 4) / sum(TE);                            % rad/s, QSM_GUI's combination
    total = field / (2*pi * 42.576 * double(p.B0));                 % ppm

    tmpl = nph;
    tmpl.hdr.dime.scl_slope = 1;  tmpl.hdr.dime.scl_inter = 0;
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(tmpl, Unwrapped, fullfile(idir, 'unwrapped.nii.gz'));
        write_intermediate(tmpl, double(Laplacian), fullfile(idir, 'laplacian.nii.gz'));
        write_intermediate(tmpl, total, fullfile(idir, 'totalfield_f64.nii.gz'));
        write_meta(idir, struct('padsize', cfg.padsize, 'sum_TE', sum(TE)));
    end

    tmpl.img = single(total);
    tmpl.hdr.dime.datatype = 16;  tmpl.hdr.dime.bitpix = 32;
    tmpl.hdr.dime.dim(1) = 3;  tmpl.hdr.dime.dim(5) = 1;
    write_niigz(tmpl, fullfile(out, 'totalfield.nii.gz'));
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
