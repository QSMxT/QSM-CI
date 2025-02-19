#!/usr/bin/env python

import numpy as np
import nibabel as nib
import h5py
import json
import os
import osfclient.cli as osf

DESCRIPTION="""
Conversion to BIDS performed by QSM-CI.

A Multi-orientation Gradient-echo MRI Dataset

144 groups of local field maps from 8 subjects, COSMOS images and six symmetric susceptibility tensor 
components from 8 subjects are provided in our dataset.

Recently, deep neural networks have shown great potentials for solving dipole inversion of quantitative 
susceptibility mapping (QSM) with improved results. However, these studies utilized their limited dataset 
for network training and inference, making the conclusion might be untrustworthy. Thus, a common dataset 
is needed for a fair comparison between different QSM reconstruction networks. Additionally, finding an 
in vivo reference susceptibility map that matches acquired single-orientation phase data remains an open 
problem. Susceptibility tensor imaging (STI) chi_{33} and Calculation of Susceptibility through Multiple 
Orientation Sampling (COSMOS) are considered reference susceptibillity candidates. However, a large 
number of multi-orientation GRE data for STI or COSMOS reconstruction is now unavailable for training 
supervised neural networks for QSM. In this study, we reported the largest multi-orientation dataset, to 
the best of our knowledge in the QSM research field, with a total of 144 scans of 8 healthy subjects 
collected using a 3D GRE sequence from the same MR scanner. In addition, the parcellation of deep gray 
matter is also provided for extracting susceptibility values automatically.

Shi, Y., Feng, R., Li, Z., Zhuang, J., Zhang, Y., & Wei, H. (2022). Towards in vivo ground truth 
susceptibility for single-orientation deep learning QSM: A multi-orientation gradient-echo MRI dataset. 
Neuroimage, 261, 119522.

osf.io/y6rc3
osf.io/yfms7
"""

def fetch(project, remote, local):
    class Args:
        def __init__(self, project, remote, local, username=None, update=True, force=False):
            self.remote = remote
            self.local = local
            self.project = project
            self.force = force
            self.username = username
            self.update = update

    args = Args(project, remote, local)
    osf.fetch(args)


bids_dir = "bids"
os.makedirs(bids_dir, exist_ok=True)

for subject_id in range(1, 9):
    print(f"Fetching sub-{subject_id}")
    sub_dir = os.path.join(bids_dir, f"sub-{subject_id}")
    os.makedirs(sub_dir, exist_ok=True)
    anat_dir = os.path.join(sub_dir, "anat")
    os.makedirs(anat_dir, exist_ok=True)
    derivatives_dir = os.path.join(bids_dir, "derivatives", "qsmci", f"sub-{subject_id}", "anat")
    os.makedirs(derivatives_dir, exist_ok=True)
    
    train_test = 'train_data' if subject_id < 6 else 'test_data'
    fetch("yfms7", f"osfstorage/{train_test}/Subject{subject_id}/cosmos1.nii.gz", os.path.join(derivatives_dir, f"sub-{subject_id}_Chimap.nii.gz"))
    fetch("yfms7", f"osfstorage/{train_test}/Subject{subject_id}/chi_tensor1.nii.gz", os.path.join(derivatives_dir, f"sub-{subject_id}_chi-tensor.nii.gz"))
    fetch("yfms7", f"osfstorage/{train_test}/Subject{subject_id}/atlas_modified1.nii.gz", os.path.join(derivatives_dir, f"sub-{subject_id}_aseg.nii.gz"))
    fetch("yfms7", f"osfstorage/{train_test}/Subject{subject_id}/H_Matrix.mat", os.path.join(derivatives_dir, f"sub-{subject_id}_H-Matrix.mat"))
    fetch("yfms7", f"osfstorage/{train_test}/Subject{subject_id}/mask1.nii.gz", os.path.join(derivatives_dir, f"sub-{subject_id}_mask.nii.gz"))
    fetch("yfms7", f"osfstorage/{train_test}/Subject{subject_id}/phi1.nii.gz", os.path.join(derivatives_dir, f"sub-{subject_id}_phi.nii.gz"))
    
    for run_num in range(1, 100):
        try:
            print(f"Fetching sub-{subject_id}_run-{run_num}")
            fetch("y6rc3", f"osfstorage/subject{subject_id}/{run_num}.mat", f"{subject_id}_{run_num}.mat")
            f = h5py.File(f"{subject_id}_{run_num}.mat", 'r')
        except:
            break
        
        B0 = np.array(f['B0'], dtype=float)[0][0]
        CF = np.array(f['CF'][0], dtype=float)
        H = np.array(f['H'][0], dtype=float)
        TEs = np.array(f['TE'][0], dtype=float)

        for echo_num in range(len(TEs)):
            print(f"Echo {echo_num}")
            data = np.array(f['data'][echo_num,:,:,:])
            TE = TEs[echo_num]
        
            real = data['real']
            imag = data['imag']
            comp = real + imag * 1j
        
            nii_phs = nib.Nifti1Image(dataobj=np.angle(comp), affine=np.eye(4))
            nii_mag = nib.Nifti1Image(dataobj=np.abs(comp), affine=np.eye(4))
            
            fname_start = os.path.join(anat_dir, f"sub-cosmos-{subject_id}_run-{run_num}_echo-{echo_num+1}_")
            nib.save(nii_phs, fname_start + "part-phase_MEGRE.nii")
            nib.save(nii_mag, fname_start + "part-mag_MEGRE.nii")
            
            bids_json = {}
            bids_json['EchoTime'] = TE
            bids_json['MagneticFieldStrength'] = B0
            bids_json_mag = bids_json.copy()
            bids_json_mag['ImageType'] = ['M', 'MAG']    
            bids_json_phs = bids_json.copy()
            bids_json_phs['ImageType'] = ['P', 'PHS', 'PHASE']
            
            with open(fname_start + "part-phase_MEGRE.json", 'w') as json_handle:
                json.dump(bids_json_phs, json_handle)
            with open(fname_start + "part-mag_MEGRE.json", 'w') as json_handle:
                json.dump(bids_json_mag, json_handle)
                
print(f"Generating details for BIDS dataset_description.json...")
dataset_description = {
    "Name" : f"A Multi-orientation Gradient-echo MRI Dataset",
    "BIDSVersion" : "1.9.0",
    "GeneratedBy" : [{
        "Name" : "qsmci",
        "Version": f"v0.1.0",
        "CodeURL" : "https://github.com/QSMxT/QSM-CI"
    }],
    "Authors" : ["Yuting Shi", "Ruimin Feng", "Zhenghao Li", "Jie Zhuang", "Yuyao Zhang", "Hongjiang Wei"]
}
print(f"Writing BIDS dataset_description.json...")
with open(os.path.join(bids_dir, 'dataset_description.json'), 'w', encoding='utf-8') as dataset_json_file:
    json.dump(dataset_description, dataset_json_file)
with open(os.path.join(bids_dir, 'derivatives', 'qsmci', 'dataset_description.json'), 'w', encoding='utf-8') as dataset_json_file:
    json.dump(dataset_description, dataset_json_file)

print(f"Writing BIDS .bidsignore file...")
with open(os.path.join(bids_dir, '.bidsignore'), 'w', encoding='utf-8') as bidsignore_file:
    bidsignore_file.write('')

print(f"Writing BIDS dataset README...")
with open(os.path.join(bids_dir, 'README'), 'w', encoding='utf-8') as readme_file:
    readme_file.write(DESCRIPTION)

