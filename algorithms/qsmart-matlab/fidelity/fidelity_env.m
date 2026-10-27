function e = fidelity_env(f)
% MATLAB and toolbox versions for the fidelity reports; optionally written to JSON file F.
    v = ver;
    pick = @(n) strjoin({v(strcmp({v.Name}, n)).Version}, '');
    [~, host] = system('hostname');
    e = struct('matlab', version, 'release', version('-release'), ...
               'images', pick('Image Processing Toolbox'), ...
               'stats', pick('Statistics and Machine Learning Toolbox'), ...
               'date', char(datetime('now', 'Format', 'yyyy-MM-dd')), 'host', strtrim(host), ...
               'threads', maxNumCompThreads);
    if nargin > 0
        fid = fopen(f, 'w'); fwrite(fid, jsonencode(e, 'PrettyPrint', true)); fclose(fid);
    end
end
