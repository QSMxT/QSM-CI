function mex_bet2(d)
% MEDI's bet2/runmex.m, with C++98 added: FSL's bet2 sources use dynamic exception
% specifications (throw(X_OptionError)), which the compiler's default C++17 rejects. Same sources,
% same include paths and define, in folder D; the mex is written there.
    old = cd(d); cleaner = onCleanup(@() cd(old));
    opt = {'-I.', ['-I' fullfile('fsl','extras','include','newmat')], ...
           ['-I' fullfile('fsl','include','meshclass')], ['-I' fullfile('fsl','extras','include','boost')], ...
           ['-I' fullfile('fsl','include','utils')], ['-I' fullfile('fsl','include','newimage')], ...
           ['-I' fullfile('fsl','include')], '-DEXPOSE_TREACHEROUS'};
    srcs = {'bet2.cpp'};
    t = dir('*.c*');
    for i = 1:numel(t)
        if ~strcmp(t(i).name, 'bet2.cpp'), srcs{end+1} = t(i).name; end %#ok<AGROW>
    end
    mex('-v', opt{:}, 'CXXFLAGS=$CXXFLAGS -std=gnu++98', srcs{:});
end
