#!/usr/bin/env bash
#DOCKER_IMAGE=vnmd/qsmxt_6.2.0:20231012

# 
# Submission: romeo_pdf_rts.sh
# 
# == References ==
# - QSMxT: Stewart AW, Robinson SD, O'Brien K, et al. QSMxT: Robust masking and artifact reduction for quantitative susceptibility mapping. Magnetic Resonance in Medicine. 2022;87(3):1289-1300. doi:10.1002/mrm.29048
# - QSMxT: Stewart AW, Bollman S, et al. QSMxT/QSMxT. GitHub; 2022. https://github.com/QSMxT/QSMxT
# - Python package - Nipype: Gorgolewski K, Burns C, Madison C, et al. Nipype: A Flexible, Lightweight and Extensible Neuroimaging Data Processing Framework in Python. Frontiers in Neuroinformatics. 2011;5. Accessed April 20, 2022. doi:10.3389/fninf.2011.00013
# - Unwrapping algorithm - ROMEO: Dymerska B, Eckstein K, Bachrata B, et al. Phase unwrapping with a rapid opensource minimum spanning tree algorithm (ROMEO). Magnetic Resonance in Medicine. 2021;85(4):2294-2308. doi:10.1002/mrm.28563
# - Background field removal - PDF: Liu, T., Khalidov, I., de Rochefort et al. A novel background field removal method for MRI using projection onto dipole fields. NMR in Biomedicine. 2011 Nov;24(9):1129-36. doi:10.1002/nbm.1670
# - QSM algorithm - RTS: Kames C, Wiggermann V, Rauscher A. Rapid two-step dipole inversion for susceptibility mapping with sparsity priors. Neuroimage. 2018 Feb 15;167:276-83. doi:10.1016/j.neuroimage.2017.11.018
# - Julia package - QSM.jl: kamesy. GitHub; 2022. https://github.com/kamesy/QSM.jl
# - Julia package - MriResearchTools: Eckstein K. korbinian90/MriResearchTools.jl. GitHub; 2022. https://github.com/korbinian90/MriResearchTools.jl
# - Python package - nibabel: Brett M, Markiewicz CJ, Hanke M, et al. nipy/nibabel. GitHub; 2019. https://github.com/nipy/nibabel
# - Python package - numpy: Harris CR, Millman KJ, van der Walt SJ, et al. Array programming with NumPy. Nature. 2020;585(7825):357-362. doi:10.1038/s41586-020-2649-2
#

# run qsmxt
qsmxt bids qsmxt_output --premade bet --bf_algorithm pdf --qsm_algorithm rts --auto_yes --use_existing_masks

# move output to expected location
mv qsmxt_output/qsm/*.nii* output/

# cleanup
rm -rf qsmxt_output

