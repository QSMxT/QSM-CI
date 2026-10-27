function fidelity_trace(inp, outdir, deps, algo, spec, report)
% List every function outside core MATLAB that recon.m reaches, pcode included, by profiling one
% licensed run. mcc can't trace into pcode, so toolbox functions only pcode calls must be named in
% recon.m's %#function pragma; this is how to find them.
    if ~exist(outdir, 'dir'), mkdir(outdir); end
    fidelity_paths(deps, spec);
    addpath(algo);
    rehash;
    profile('on');
    recon(inp, outdir);
    profile('off');
    s = profile('info');
    tbroot = [fullfile(matlabroot, 'toolbox') filesep];
    core = [fullfile(matlabroot, 'toolbox', 'matlab') filesep];
    rows = {};
    for k = 1:numel(s.FunctionTable)
        f = s.FunctionTable(k);
        if startsWith(f.FileName, tbroot) && ~startsWith(f.FileName, core)
            tb = extractBetween(f.FileName, tbroot, filesep);
            rows{end+1} = sprintf('%-20s %-40s %s', tb{1}, f.FunctionName, f.FileName); %#ok<AGROW>
        end
    end
    rows = unique(rows);
    deprows = {};
    for k = 1:numel(s.FunctionTable)
        f = s.FunctionTable(k);
        if startsWith(f.FileName, [deps filesep])
            deprows{end+1} = sprintf('%-40s %s', f.FunctionName, f.FileName(numel(deps)+2:end)); %#ok<AGROW>
        end
    end
    deprows = unique(deprows);
    fid = fopen(report, 'w');
    fprintf(fid, '# toolbox functions reached (outside toolbox/matlab), %s\n', version);
    fprintf(fid, '%s\n', rows{:});
    fprintf(fid, '\n# dependency code reached (MATLAB code only: pcode shows as its own name)\n');
    fprintf(fid, '%s\n', deprows{:});
    fclose(fid);
    type(report);
end
