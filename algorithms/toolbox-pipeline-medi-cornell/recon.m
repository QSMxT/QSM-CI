function recon(inp, out)
% QSM-CI `pipeline` span in MATLAB: the MEDI toolbox 2024.11.26's own pipeline (README.m), from the
% echoes to χ, as the reference for QSMxT's `medi-toolbox` pipeline (QSMxT/QSM-CI#421).
% Reads <inp>/phase.nii.gz (rad, echoes on dim 4), magnitude.nii.gz and params.json; writes
% <out>/chimap.nii.gz (ppm). The chain is README.m's, step for step:
%   iField = mag·e^(−i·phase)                (the complex echoes, QSM-CI's phase convention, as
%                                             fit-ppm-complex-cornell builds them)
%   [iFreq_raw, N_std] = Fit_ppm_complex(iField)
%   iMag  = sqrt(sum(abs(iField).^2, 4))
%   iFreq = unwrapPhase(iMag, iFreq_raw, matrix_size)
%   Mask  = BET(iMag, matrix_size, voxel_size)          (MEDI's bet2 mex, its defaults)
%   RDF   = PDF(iFreq, N_std, Mask, matrix_size, voxel_size, B0_dir)
%   R2s   = arlo(TE, abs(iField));  Mask_CSF = extract_CSF(R2s, Mask, voxel_size)
%   QSM   = MEDI_L1('lambda', 1000, 'lambda_CSF', 100, 'merit', 'smv', 5)
% CF is the scanner's centre frequency, as README.m reads it from the DICOM header: params.json's
% ImagingFrequency (MHz) when the dataset has it, else γ·B0 (and intermediates.json says which).
% No referencing after MEDI_L1: MEDI+0's CSF term is the only one.
%
% Bundled: Jimmy Shen NIfTI toolbox, Cornell MEDI toolbox 2024.11.26 with its bet2 mex compiled
% (BUILD.md). OS gunzip/gzip (compiled binaries have no JVM).
%
% Intermediates (QSMCI_INTERMEDIATES, a directory or 1 for <out>/intermediates), under the names
% QSMxT's candidate writes (CONTRACT.md "Intermediates"): mask (BET's), totalfield (ppm),
% localfield (ppm, PDF's RDF), r2star (Hz) and mask_csf; also ifreq_raw and n_std (README.m's
% units). There is no chimap_unreferenced: MEDI_L1 references inside the inversion.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    B0_dir = p.B0_dir(:)'; B0_dir = B0_dir / norm(B0_dir);
    voxel_size = p.voxel_size(:)';
    TE  = double(p.TE(:)');

    nph = read_niigz(fullfile(inp, 'phase.nii.gz'));
    ph  = double(nph.img);
    mag = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    nte = size(ph, 4);
    if nte ~= numel(TE) || size(mag, 4) ~= nte
        error('recon:te', 'phase has %d echoes, magnitude %d, params.json %d echo times', ...
              nte, size(mag, 4), numel(TE));
    end
    if nte > 2 && max(abs(diff(diff(TE)))) > 1e-6 * max(TE)
        error('recon:te', 'Fit_ppm_complex needs evenly spaced echoes (TE = %s)', mat2str(TE));
    end
    matrix_size = [size(ph, 1) size(ph, 2) size(ph, 3)];
    if isfield(p, 'ImagingFrequency') && ~isempty(p.ImagingFrequency)
        CF = double(p.ImagingFrequency) * 1e6;  cf_source = 'ImagingFrequency';
    else
        CF = 42.576e6 * double(p.B0);            cf_source = 'gamma*B0';
    end
    if nte > 1, delta_TE = TE(2) - TE(1); else, delta_TE = TE(1); end
    to_ppm = 1e6 / (2*pi * CF * delta_TE);

    % --- README.m ---
    iField = mag .* exp(-1i * ph);
    [iFreq_raw, N_std] = Fit_ppm_complex(iField);
    iMag  = sqrt(sum(abs(iField).^2, 4));
    iFreq = unwrapPhase(iMag, iFreq_raw, matrix_size);
    Mask  = BET(iMag, matrix_size, voxel_size);
    RDF   = PDF(iFreq, N_std, Mask, matrix_size, voxel_size, B0_dir);
    R2s   = arlo(TE, abs(iField));
    Mask_CSF = extract_CSF(R2s, Mask, voxel_size);

    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));
    save('RDF.mat', 'RDF', 'iFreq', 'iFreq_raw', 'iMag', 'N_std', 'Mask', 'matrix_size', ...
         'voxel_size', 'delta_TE', 'CF', 'B0_dir', 'Mask_CSF', 'R2s');
    [QSM, ~, ~, resultsfile] = MEDI_L1('lambda', 1000, 'lambda_CSF', 100, 'merit', 'smv', 5);   % ppm
    % MEDI_L1 zeroes χ outside the mask it inverted on (with SMV, the eroded mask; MEDI_L1.m:201)
    % and then subtracts the CSF mean everywhere (:204-206), so that ring holds −mean. Keep χ zero
    % outside the inverted mask, as medi-cornell does and as QSM.rs's MEDI leaves it.
    Mask_inv = load(resultsfile, 'Mask');  QSM = QSM .* (Mask_inv.Mask > 0);
    cd(old);

    tmpl = nph;
    tmpl.hdr.dime.dim(1) = 3;  tmpl.hdr.dime.dim(5) = 1;
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(tmpl, double(Mask), fullfile(idir, 'mask.nii.gz'));
        write_intermediate(tmpl, iFreq * to_ppm, fullfile(idir, 'totalfield.nii.gz'));
        write_intermediate(tmpl, RDF * to_ppm, fullfile(idir, 'localfield.nii.gz'));
        if ~isempty(R2s), write_intermediate(tmpl, R2s, fullfile(idir, 'r2star.nii.gz')); end
        write_intermediate(tmpl, double(Mask_CSF), fullfile(idir, 'mask_csf.nii.gz'));
        write_intermediate(tmpl, iFreq_raw, fullfile(idir, 'ifreq_raw.nii.gz'));
        write_intermediate(tmpl, N_std, fullfile(idir, 'n_std.nii.gz'));
        write_meta(idir, struct('CF', CF, 'cf_source', cf_source, 'delta_TE', delta_TE));
    end
    tmpl.img = single(QSM);
    tmpl.hdr.dime.datatype = 16;  tmpl.hdr.dime.bitpix = 32;
    tmpl.hdr.dime.scl_slope = 1;  tmpl.hdr.dime.scl_inter = 0;
    write_niigz(tmpl, fullfile(out, 'chimap.nii.gz'));
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
% No pcode here: mcc traces every call. These record where the MEDI functions resolved.
    tb = {'Fit_ppm_complex', 'unwrapPhase', 'mexUnwrap', 'BET', 'bet2', 'PDF', 'arlo', ...
          'extract_CSF', 'MEDI_L1', 'parse_QSM_input', 'gradient_mask', 'dataterm_mask', ...
          'cgsolve', 'reg_CSF', 'SMV', 'sphere_kernel'};
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
% intermediates.json: M plus the MATLAB version, the thread count, and where each function in
% toolbox_functions() resolved.
    tb = toolbox_functions();
    m.matlab = version;
    m.threads = maxNumCompThreads;
    m.resolved = cell2struct(cellfun(@which, tb, 'UniformOutput', false), tb, 2);
    fid = fopen(fullfile(idir, 'intermediates.json'), 'w');
    fwrite(fid, jsonencode(m));
    fclose(fid);
end
