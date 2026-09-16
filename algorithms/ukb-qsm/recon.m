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

    [chi, mask_vsf] = UKBiobank_QSM_core(phase, mask, TEs, B0, H, vox);
    chi = double(chi) .* double(mask_vsf);
    if any(po)
        chi = chi(1:sz0(1), 1:sz0(2), 1:sz0(3));
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
