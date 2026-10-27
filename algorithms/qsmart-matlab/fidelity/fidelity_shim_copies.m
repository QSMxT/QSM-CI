function names = fidelity_shim_copies(shimdir, dest)
% Copy every shim in SHIMDIR to DEST as shim_<name>.m, renaming the function and every call to a
% sibling shim (imclose -> shim_imdilate/shim_imerode, ...). The shims shadow the toolbox names, so
% this is what lets one MATLAB session call the shim and the licensed toolbox function side by side.
% Returns the shim names (without the prefix).
    d = dir(fullfile(shimdir, '*.m'));
    names = sort(erase({d.name}, '.m'));
    if ~exist(dest, 'dir'), mkdir(dest); end
    for k = 1:numel(names)
        txt = fileread(fullfile(shimdir, [names{k} '.m']));
        for j = 1:numel(names)
            txt = regexprep(txt, ['(?<![\w''])' names{j} '(?![\w''])'], ['shim_' names{j}]);
        end
        fid = fopen(fullfile(dest, ['shim_' names{k} '.m']), 'w');
        fwrite(fid, txt); fclose(fid);
    end
    rehash;
end
