function fidelity_paths(base, spec)
% Put the assembled dependencies on the MATLAB path in the order SPEC lists them (first = highest
% priority). SPEC is the algorithm's FID_MATLAB_PATH: folder names under BASE, separated by spaces;
% a leading '+' adds the folder with its subfolders (genpath).
    items = strsplit(strtrim(spec));
    for k = numel(items):-1:1          % addpath prepends, so add the last one first
        d = items{k};
        if isempty(d), continue; end
        if d(1) == '+'
            addpath(genpath(fullfile(base, d(2:end))));
        else
            addpath(fullfile(base, d));
        end
    end
end
