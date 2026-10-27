function out = fidelity_trace_call(name, args, nout)
% Body of the generated tracers (fidelity_trace_setup.m): run shim_<name> and the toolbox <name>,
% log the comparison, return the shim's outputs.
    global QSMCI_FIDELITY %#ok<GVMIS>
    F = QSMCI_FIDELITY;
    out = cell(1, nout);
    t = tic; [out{:}] = feval(['shim_' name], args{:}); t_shim = toc(t);

    % The toolbox call runs with the tracers off the path, so toolbox internals that call other
    % shadowed names (imbothat -> imclose, ...) get the toolbox versions too.
    rmpath(F.tdir);
    note = ''; t_ref = NaN; ref = [];
    try
        rargs = args;
        for k = 1:numel(rargs)
            if isstruct(rargs{k}) && isfield(rargs{k}, 'nhood'), rargs{k} = strel(rargs{k}.nhood); end
        end
        t = tic; ref = feval(name, rargs{:}); t_ref = toc(t);
    catch e
        note = ['toolbox error: ' e.message];
    end
    addpath(F.tdir);

    QSMCI_FIDELITY.n = F.n + 1;
    st = dbstack;
    caller = '?';
    if numel(st) >= 3, caller = sprintf('%s:%d', st(3).name, st(3).line); end
    if isempty(note)
        c = fidelity_compare(out{1}, ref);
    else
        c = struct('identical', false, 'maxabs', NaN, 'maxrel', NaN, 'ndiff', NaN, 'numel', NaN);
    end
    o = out{1}; if isstruct(o) && isfield(o, 'nhood'), o = o.nhood; end
    fprintf(F.fid, '%s\t%d\t%s\t%s\t%s\t%s\t%d\t%.6g\t%.6g\t%d\t%d\t%.3f\t%.3f\t%s\n', name, ...
        QSMCI_FIDELITY.n, caller, describe(args), class(o), mat2str(size(o)), c.identical, ...
        c.maxabs, c.maxrel, c.ndiff, c.numel, t_shim, t_ref, note);

    if ~c.identical && ~any(strcmp(F.saved, name))
        w = whos('args');
        if w.bytes < 2e9
            shim_out = out{1}; toolbox_out = ref; %#ok<NASGU>
            save(fullfile(F.logdir, ['repro_' name '.mat']), 'name', 'args', 'shim_out', ...
                 'toolbox_out', 'caller', '-v7.3');
        end
        QSMCI_FIDELITY.saved{end+1} = name;
    end
end

function s = describe(args)
% Short signature: class+size for arrays, the value for strings and small numerics.
    p = cell(1, numel(args));
    for k = 1:numel(args)
        a = args{k};
        if ischar(a) || isstring(a)
            p{k} = ['''' char(a) ''''];
        elseif isstruct(a) && isfield(a, 'nhood')
            p{k} = sprintf('se[%s, %d px]', mat2str(size(a.nhood)), nnz(a.nhood));
        elseif (isnumeric(a) || islogical(a)) && numel(a) <= 6
            p{k} = mat2str(reshape(double(a), 1, []), 6);
            if ~isvector(a) && ~isempty(a), p{k} = sprintf('%s%s', p{k}, mat2str(size(a))); end
        else
            p{k} = sprintf('%s%s', class(a), mat2str(size(a)));
        end
    end
    s = strjoin(p, ', ');
end
