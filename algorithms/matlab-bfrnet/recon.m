function recon(inp, out)
% QSM-CI `bfr` stage in MATLAB — BFRnet deep-learning background field removal.
% Reads <inp>/totalfield.nii.gz (ppm, 3D) + mask + params, writes <out>/localfield.nii.gz (ppm).
%
% BFRnet is a 3D Octave-convolution DAG network (MATLAB Deep Learning Toolbox) that predicts the
% BACKGROUND field from the total field; the local tissue field is total − background, masked.
% Everything is in ppm — the network never sees TE/B0/B0_dir, so params.json is read only for
% completeness (voxel_size is carried by the NIfTI header, not needed by the net). See BUILD.md.
%
% The trained network `BFRnet.mat` (variable `net`) is bundled at compile time with `mcc -a` and
% is NOT committed to git (fetched from the authors' Dropbox — see BUILD.md). Bundled NIfTI toolbox
% + a `padarray` IPT shim (the Runtime has no Image Processing Toolbox) + OS gunzip/gzip (no JVM).
% Optional <inp>/config.json is accepted but BFRnet has no tunables.

    % --- load inputs -----------------------------------------------------------------------------
    nii  = read_niigz(fullfile(inp, 'totalfield.nii.gz'));
    tfs  = double(nii.img);
    Mask = double(getfield(read_niigz(fullfile(inp, 'mask.nii.gz')), 'img')) > 0.5;
    if ndims(tfs) > 3, tfs = tfs(:,:,:,1); end
    tfs  = tfs .* Mask;                                   % net was trained on masked total field

    % --- locate the bundled network --------------------------------------------------------------
    % mcc places `-a`-bundled data files next to the deployed binary; ctfroot resolves that dir at
    % run time. Fall back to the source dir for uncompiled (interpreted) testing.
    netfile = locate_net();
    S   = load(netfile);                                 % `net` = a trained DAGNetwork/dlnetwork
    net = S.net;

    % --- pad to a multiple of 8 (BFRnet's 3 pooling levels need dims divisible by 8) --------------
    sz0 = size(tfs);
    pad = mod(8 - mod(sz0, 8), 8);                        % voxels to add per axis (0 if already ok)
    tfp = padarray(tfs, pad, 0, 'post');

    % --- rebuild the input layer at this image size and predict the background field -------------
    imSize   = size(tfp);
    newInput = image3dInputLayer(imSize, 'Name', 'ImageInputLayer', 'Normalization', 'none');
    lg       = replaceLayer(layerGraph(net), 'ImageInputLayer', newInput);
    L1Net    = assembleNetwork(lg);

    bkg = predict(L1Net, tfp, 'ExecutionEnvironment', 'cpu');   % background field, ppm
    bkg = double(bkg);
    bkg = bkg(1:sz0(1), 1:sz0(2), 1:sz0(3));             % crop the post-pad back off

    local = (tfs - bkg) .* Mask;                          % local tissue field, ppm

    % --- write output ----------------------------------------------------------------------------
    nii.img = single(local);
    nii.hdr.dime.datatype = 16;  nii.hdr.dime.bitpix = 32;
    nii.hdr.dime.dim(1) = 3;  nii.hdr.dime.dim(5) = 1;
    write_niigz(nii, fullfile(out, 'localfield.nii.gz'));
end

function f = locate_net()
    cands = {fullfile(ctfroot, 'BFRnet.mat'), ...
             fullfile(fileparts(mfilename('fullpath')), 'BFRnet.mat'), ...
             'BFRnet.mat'};
    for i = 1:numel(cands)
        if exist(cands{i}, 'file'), f = cands{i}; return; end
    end
    error('recon:netMissing', 'BFRnet.mat not found (bundle it with mcc -a; see BUILD.md).');
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
