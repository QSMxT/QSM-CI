#!/usr/bin/env bash
#DOCKER_IMAGE=vnmd/qsmxt_6.2.0:20231012

# == References ==
# - QSMxT: Stewart AW, Robinson SD, O'Brien K, et al. QSMxT: Robust masking and artifact reduction for quantitative susceptibility mapping. Magnetic Resonance in Medicine. 2022;87(3):1289-1300. doi:10.1002/mrm.29048
# - QSMxT: Stewart AW, Bollman S, et al. QSMxT/QSMxT. GitHub; 2022. https://github.com/QSMxT/QSMxT
# - Python package - Nipype: Gorgolewski K, Burns C, Madison C, et al. Nipype: A Flexible, Lightweight and Extensible Neuroimaging Data Processing Framework in Python. Frontiers in Neuroinformatics. 2011;5. Accessed April 20, 2022. doi:10.3389/fninf.2011.00013
# - Unwrapping algorithm - Laplacian: Schofield MA, Zhu Y. Fast phase unwrapping algorithm for interferometric applications. Optics letters. 2003 Jul 15;28(14):1194-6. doi:10.1364/OL.28.001194")
# - Unwrapping algorithm - Laplacian: Zhou D, Liu T, Spincemaille P, Wang Y. Background field removal by solving the Laplacian boundary value problem. NMR in Biomedicine. 2014 Mar;27(3):312-9. doi:10.1002/nbm.3064")
# - QSM algorithm - NeXtQSM: Cognolato, F., O'Brien, K., Jin, J. et al. (2022). NeXtQSM—A complete deep learning pipeline for data-consistent Quantitative Susceptibility Mapping trained with hybrid data. Medical Image Analysis, 102700. doi:10.1016/j.media.2022.102700
# - Julia package - MriResearchTools: Eckstein K. korbinian90/MriResearchTools.jl. GitHub; 2022. https://github.com/korbinian90/MriResearchTools.jl
# - Python package - nibabel: Brett M, Markiewicz CJ, Hanke M, et al. nipy/nibabel. GitHub; 2019. https://github.com/nipy/nibabel
# - Python package - numpy: Harris CR, Millman KJ, van der Walt SJ, et al. Array programming with NumPy. Nature. 2020;585(7825):357-362. doi:10.1038/s41586-020-2649-2

# run qsmxt
qsmxt bids qsmxt_output \
    --subjects $BIDS_SUBJECT \
    --sessions $BIDS_SESSION \
    --runs $BIDS_RUN \
    --premade nextqsm \
    --unwrapping_algorithm laplacian \
    --combine_phase off \
    --auto_yes \
    --use_existing_masks

# move output to expected location
mv qsmxt_output/qsm/*.nii* output/

