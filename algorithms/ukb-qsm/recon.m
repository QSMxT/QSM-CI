function recon(inp, out)
% QSM-CI `end-to-end` stage — the UK Biobank QSM pipeline.
%
% This file is only the adapter: read the QSM-CI artifacts, call the upstream reconstruction
% in ukb/UKBiobank_QSM_core.m, write the result. The pipeline itself is upstream's code (Wang,
% Tendler & Miller, Oxford, Apache-2.0) with two marked edits, documented in that file and in
% BUILD.md: N echoes instead of two, and ppm output instead of ppb.
%
% Reads  <inp>/phase.nii.gz (radians, x,y,z,echo), mask.nii.gz, params.json
% Writes <out>/chimap.nii.gz in ppm.
%
% Coil combination (MCPC-3D-S, PRELUDE on the Hermitian inner product) is upstream of this
% stage; QSM-CI supplies combined phase, so it is not part of the submission.
%
% Bundled at build time (BUILD.md): Jimmy Shen NIfTI toolbox, STI Suite v3 Core_Functions_P (pcode),
% the vendored ukb/ code, and the real Image Processing Toolbox functions they call (compiled from
% licensed MATLAB; the MATLAB Runtime includes their runtime components).
%
% Optional intermediates (fidelity checks, ../../fidelity/matlab/README.md): set QSMCI_INTERMEDIATES
% to a directory, or to 1 for <out>/intermediates. recon then also writes, in float64 on the input
% grid: the two phase-variance maps, the trimmed mask, the combined unwrapped phase, V-SHARP's local
% field and mask, the final mask, and the final χ, plus intermediates.json (the effective TE, MATLAB
% version, thread count, and where each toolbox function resolved). Unset (the default), nothing
% changes.

% Toolbox functions STI Suite's pcode calls, which mcc can't trace into: name them so they are
% bundled (the UKB code's own calls are traced). Found by profiling a licensed run
% (../../fidelity/matlab/README.md, `trace`); keep toolbox_functions() below in step.
%#function bwareaopen imclose imdilate imerode imfill padarray strel

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    H   = p.B0_dir(:)'; H = H / norm(H);
    vox = p.voxel_size(:)';
    B0  = p.B0;                                  % tesla
    TEs = p.TE(:)' * 1000;                       % contract is seconds; upstream works in ms
                                                 % (its T2* constant is 40 ms, and STI Suite's
                                                 % QSM_iLSQR takes TE in ms)

    nii   = read_niigz(fullfile(inp, 'phase.nii.gz'));
    phase = double(nii.img);                                        % radians
    mask  = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;
    if size(phase, 4) ~= numel(TEs)
        error('recon: %d phase volumes but %d echo times', size(phase, 4), numel(TEs));
    end

    % EDIT (adapter): STI Suite's kernels index assuming even matrix dimensions (the same constraint
    % ilsqr-sti handles). UK Biobank's own 256x288x48 is even throughout, so upstream
    % never meets this; other datasets can be odd. Zero-pad to even before the call and
    % crop back after — lossless for the FFT model, and it leaves the vendored code alone.
    sz0 = size(mask);
    po  = mod(sz0, 2);
    if any(po)
        phase = padarray(phase, [po 0], 0, 'post');
        mask  = padarray(mask,  po,     0, 'post');
    end

    [chi, mask_vsf, I] = UKBiobank_QSM_core(phase, mask, TEs, B0, H, vox);
    chi = double(chi) .* double(mask_vsf);
    if any(po)
        chi = chi(1:sz0(1), 1:sz0(2), 1:sz0(3));
    end

    idir = intermediates_dir(out);
    if ~isempty(idir)
        I.mask_final = mask_vsf;
        I.chimap = chi;
        crop = @(a) a(1:sz0(1), 1:sz0(2), 1:sz0(3));
        for f = {'map', 'map2', 'mask', 'phs_comb', 'dB_vsf', 'mask_vsharp', 'mask_final', 'chimap'}
            write_intermediate(nii, crop(I.(f{1})), fullfile(idir, [f{1} '.nii.gz']));
        end
        write_meta(idir, struct('TE_ms', I.TE));
    end

    nii.img = single(chi);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3;  nii.hdr.dime.dim(5) = 1;
    write_niigz(nii, fullfile(out, 'chimap.nii.gz'));
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
    tb = {'bwareaopen', 'imclose', 'imdilate', 'imerode', 'imfill', 'padarray', 'strel'};
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
