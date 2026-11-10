function recon(inp, out)
% QSM-CI `pipeline` span in MATLAB: the χ-separation toolbox v1.1.3's own pipeline
% (Chisep_script.m), from the echoes to χ+ and χ−, as the reference for QSMxT's `chi-sep-ilsqr` and
% `chi-sep-medi` pipelines (QSMxT/QSM-CI#421). `method` (config.json) picks the χ-separation:
% ilsqr (the default) or medi. Reads <inp>/phase.nii.gz (rad, echoes on dim 4), magnitude.nii.gz,
% r2prime.nii.gz (Hz: the toolbox takes a measured R2′) and params.json; writes chi-para.nii.gz,
% chi-dia.nii.gz (ppm) and chimap.nii.gz (the iLSQR QSM the script makes, ppm).
%
% The chain is the script's, step for step:
%   Tukey window (tukey_fac 0.4, 0 for Philips) on mag·e^(i·phase)
%   mag = RSS over echoes;  [~, N_std] = Preprocessing4Phase(mag, phase)
%   mask_brain = BET(mag, ...)                         (MEDI's bet2 mex, its defaults)
%   r2star = r2star_arlo(...) if use_arlo(TE), else r2star_nnls(...)   (TE in ms)
%   ROMEO (mritools CLI) with the script's parameters: TE in ms, magnitude, the BET mask,
%     phase_offset_correction on, '-q'; NaN → 0
%   weighted echo average, W = TE·e^(−TE/0.04), field_map = Σ(W·φ)/ΣW / TE_eff · ΔTE · mask (rad)
%   [local_field, mask_brain_new] = V_SHARP(field_map, mask_brain, 'smvsize', 12)
%   QSM = QSM_iLSQR(local_field, mask_brain_new, 'TE', ΔTE·1e3, 'B0', B0, 'H', B0_dir,
%                   'padsize', [12 12 12], 'voxelsize', voxel_size)
%   ilsqr: chi_sep_iLSQR(mag, local_field_hz, r2prime, mask_brain_new, params, {qsm, N_std})
%   medi:  chi_sep_MEDI(mag, local_field_hz, r2prime, N_std, mask_brain_new, params
%                       + lambda 1, lambda_CSF 1, {qsm, mask_CSF, N_std}), with
%          mask_CSF = extract_CSF(r2star, mask_brain_new, voxel_size): the script leaves that
%          line commented out, but its own comment says χ-sep-MEDI needs it, and the call fails
%          without it.
% CF is params.json's ImagingFrequency (MHz) when present, else γ·B0 (the script takes CF from
% the scanner). Phase: QSM-CI's convention, which the script takes as is (it would negate the
% field only "if the phase rotation is in the opposite direction").
%
% Bundled: NIfTI toolbox, STI Suite 3.0 (pcode), MEDI toolbox 2024.11.26 (BET with its bet2 mex,
% extract_CSF), the χ-separation toolbox v1.1.3 (pcode), and mritools 4.7.1's `romeo` binary
% (BUILD.md). OS gunzip/gzip.
%
% Intermediates (QSMCI_INTERMEDIATES), under the names QSMxT's candidate writes: mask (BET's),
% totalfield (ppm), localfield (ppm, V-SHARP's), r2star (Hz), mask_vsharp, n_std.

    p   = jsondecode(fileread(fullfile(inp, 'params.json')));
    cfg = struct('method', 'ilsqr');
    cf_file = fullfile(inp, 'config.json');
    if exist(cf_file, 'file')
        u = jsondecode(fileread(cf_file));
        for f = fieldnames(u)', cfg.(f{1}) = u.(f{1}); end
    end
    B0_strength = double(p.B0);
    B0_direction = p.B0_dir(:)'; B0_direction = B0_direction / norm(B0_direction);
    voxel_size = p.voxel_size(:)';
    TE = double(p.TE(:)');
    delta_TE = TE(2) - TE(1);
    if isfield(p, 'ImagingFrequency') && ~isempty(p.ImagingFrequency)
        CF = double(p.ImagingFrequency) * 1e6;  cf_source = 'ImagingFrequency';
    else
        CF = 42.5774e6 * B0_strength;           cf_source = 'gamma*B0';
    end
    manufacturer = '';
    if isfield(p, 'Manufacturer'), manufacturer = lower(char(p.Manufacturer)); end

    nph = read_niigz(fullfile(inp, 'phase.nii.gz'));
    phs_multi_echo = double(nph.img);
    mag_multi_echo = double(getfield(read_niigz(fullfile(inp, 'magnitude.nii.gz')), 'img'));
    r2prime = double(getfield(read_niigz(fullfile(inp, 'r2prime.nii.gz')), 'img'));

    % --- Chisep_script.m ---
    tukey_fac = 0.4;                                     % "Siemens, GE: 0.4, Philips: 0"
    if contains(manufacturer, 'philips'), tukey_fac = 0; end
    img_tukey = tukey_windowing(mag_multi_echo .* exp(1i * phs_multi_echo), tukey_fac);
    mag_multi_echo = abs(img_tukey);
    phs_multi_echo = angle(img_tukey);
    mag = sqrt(sum(abs(mag_multi_echo).^2, 4));
    [~, N_std] = Preprocessing4Phase(mag_multi_echo, phs_multi_echo);

    matrix_size = size(mag);
    mask_brain = BET(mag, matrix_size, voxel_size);

    if use_arlo(TE)
        r2star = r2star_arlo(mag_multi_echo, TE * 1000, mask_brain);
    else
        r2star = r2star_nnls(mag_multi_echo, TE * 1000, mask_brain);
    end

    wd = tempname; mkdir(wd); old = cd(wd); cleaner = onCleanup(@() cd(old));
    parameters.TE = TE * 1000;
    parameters.mag = mag_multi_echo;
    parameters.mask = double(mask_brain);
    parameters.calculate_B0 = false;
    parameters.phase_offset_correction = 'on';
    parameters.voxel_size = voxel_size;
    parameters.additional_flags = '-q';
    parameters.output_dir = 'romeo_tmp';
    romeo = getenv('MRITOOLS_ROMEO');                    % the image's mritools `romeo` binary
    if ~isempty(romeo), parameters.command = romeo; end
    mkdir(parameters.output_dir);
    [unwrapped_phase, ~] = ROMEO(double(phs_multi_echo), parameters);
    unwrapped_phase(isnan(unwrapped_phase)) = 0;
    cd(old);

    t2s_roi = 0.04;
    W = (TE) .* exp(-(TE) / t2s_roi);
    weightedSum = 0;
    TE_eff = 0;
    for echo = 1:size(unwrapped_phase, 4)
        weightedSum = weightedSum + W(echo) * unwrapped_phase(:,:,:,echo) ./ sum(W);
        TE_eff = TE_eff + W(echo) * (TE(echo)) ./ sum(W);
    end
    field_map = weightedSum / TE_eff * delta_TE .* mask_brain;

    smv_size = 12;
    [local_field, mask_brain_new] = V_SHARP(field_map, mask_brain, 'voxelsize', voxel_size, 'smvsize', smv_size);
    local_field_hz = local_field / (2*pi*delta_TE);

    pad_size = [12, 12, 12];
    QSM = QSM_iLSQR(local_field, mask_brain_new, 'TE', delta_TE*1e3, 'B0', B0_strength, ...
                    'H', B0_direction, 'padsize', pad_size, 'voxelsize', voxel_size);

    params.b0_dir = B0_direction;
    params.CF = CF;
    params.voxel_size = voxel_size;
    switch lower(char(cfg.method))
        case 'ilsqr'
            option_data.qsm = QSM;
            option_data.N_std = N_std;
            [x_para, x_dia, ~] = chi_sep_iLSQR(mag, local_field_hz, r2prime, mask_brain_new, params, option_data);
        case 'medi'
            mask_CSF = extract_CSF(r2star, mask_brain_new, voxel_size);
            params.lambda = 1;
            params.lambda_CSF = 1;
            option_data.qsm = QSM;
            option_data.mask_CSF = mask_CSF;
            option_data.N_std = N_std;
            [x_para, x_dia, ~] = chi_sep_MEDI(mag, local_field_hz, r2prime, N_std, mask_brain_new, params, option_data);
        otherwise
            error('recon:method', 'method must be ilsqr or medi, got %s', char(cfg.method));
    end

    tmpl = nph;
    tmpl.hdr.dime.dim(1) = 3;  tmpl.hdr.dime.dim(5) = 1;
    to_ppm = 1e6 / (2*pi * CF * delta_TE);
    idir = intermediates_dir(out);
    if ~isempty(idir)
        write_intermediate(tmpl, double(mask_brain), fullfile(idir, 'mask.nii.gz'));
        write_intermediate(tmpl, double(mask_brain_new), fullfile(idir, 'mask_vsharp.nii.gz'));
        write_intermediate(tmpl, field_map * to_ppm, fullfile(idir, 'totalfield.nii.gz'));
        write_intermediate(tmpl, local_field * to_ppm, fullfile(idir, 'localfield.nii.gz'));
        write_intermediate(tmpl, r2star, fullfile(idir, 'r2star.nii.gz'));
        write_intermediate(tmpl, N_std, fullfile(idir, 'n_std.nii.gz'));
        write_meta(idir, struct('CF', CF, 'cf_source', cf_source, 'tukey_fac', tukey_fac, ...
            'method', char(cfg.method)));
    end
    write_niigz(as_float(tmpl, QSM), fullfile(out, 'chimap.nii.gz'));
    write_niigz(as_float(tmpl, x_para), fullfile(out, 'chi-para.nii.gz'));
    write_niigz(as_float(tmpl, x_dia), fullfile(out, 'chi-dia.nii.gz'));
end

function nii = as_float(tmpl, a)
    nii = tmpl; nii.img = single(a);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.scl_slope = 1;  nii.hdr.dime.scl_inter = 0;
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
    tb = {'tukey_windowing', 'Preprocessing4Phase', 'BET', 'bet2', 'use_arlo', 'r2star_arlo', ...
          'r2star_nnls', 'extract_CSF', 'ROMEO', 'V_SHARP', 'QSM_iLSQR', 'chi_sep_iLSQR', ...
          'chi_sep_MEDI'};
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
