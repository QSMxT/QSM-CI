# lbv-cornell: fidelity harness settings (../../../fidelity/matlab/README.md). Sourced by bash.
FID_SIF=matlab-medi-lbv
FID_SOURCES="FID_MEDI FID_NIFTI"   # MEDI_toolbox-2024.11.26 (the folder holding functions/); Jimmy Shen NIfTI_20140122
FID_MATLAB_PATH="nifti medi"
FID_MCC_A="medi/mexMGv6.mexa64"    # the mex LBV.m calls, compiled from the shipped source (BUILD.md)
FID_WHICH="LBV mexMGv6"

fid_assemble() {
    local D=$1
    rm -rf "$D"; mkdir -p "$D/medi"
    cp -r "$FID_NIFTI" "$D/nifti"
    cp "$FID_MEDI"/functions/_LBV/{LBV.m,mexMGv6.cpp} "$D/medi/"
}

# BUILD.md §2: the toolbox's mexMGv6.mexa64 predates its mexMGv6.cpp (it returns no `interior`,
# which LBV.m asks for), so the mex is compiled from the shipped source.
fid_build_hook() { mat "cd('$1/medi'); mex mexMGv6.cpp"; }
fid_setup_hook() { mat "cd('$1/medi'); mex mexMGv6.cpp"; }
