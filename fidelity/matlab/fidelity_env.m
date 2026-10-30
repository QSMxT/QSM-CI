function e = fidelity_env(f)
% MATLAB and toolbox versions for the fidelity reports; optionally written to JSON file F.
    v = ver;
    tb = struct();
    for k = 1:numel(v)
        n = matlab.lang.makeValidName(v(k).Name);
        tb.(n) = v(k).Version;
    end
    [~, host] = system('hostname');
    e = struct('matlab', version, 'release', version('-release'), 'toolboxes', tb, ...
               'date', char(datetime('now', 'Format', 'yyyy-MM-dd')), 'host', strtrim(host), ...
               'threads', maxNumCompThreads);
    if nargin > 0
        fid = fopen(f, 'w'); fwrite(fid, jsonencode(e, 'PrettyPrint', true)); fclose(fid);
    end
end
