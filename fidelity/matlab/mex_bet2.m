function mex_bet2(d)
% MEDI's bet2/runmex.m, with C++98 added: FSL's bet2 sources use dynamic exception
% specifications (throw(X_OptionError)), which the compiler's default C++17 rejects. Same sources,
% same include paths and define, in folder D; the mex is written there. libstdc++ is linked
% statically: the host's g++ (11 on Bunya) needs a newer libstdc++ than the one MATLAB R2023b
% loads first, so a dynamically linked mex fails to load and BET.m reports it as missing.
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
    mex('-v', opt{:}, 'CXXFLAGS=$CXXFLAGS -std=gnu++98', ...
        'LDFLAGS=$LDFLAGS -static-libstdc++ -static-libgcc', srcs{:});
end
