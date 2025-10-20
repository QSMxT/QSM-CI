#!/usr/bin/env python

"""
eval.py

This module provides functions to compute various error metrics between 3D predicted and reference 
data arrays. The primary function, `all_metrics()`, returns a dictionary of all computed metrics.

Metrics included: RMSE, NRMSE, HFEN, XSIM, MAD, CC, NMI, GXE.

Example:
    >>> import numpy as np
    >>> import metrics
    >>> pred_data = np.random.rand(100, 100, 100)
    >>> ref_data = np.random.rand(100, 100, 100)
    >>> roi = np.random.randint(0, 2, size=(100, 100, 100), dtype=bool)
    >>> metrics = metrics.all_metrics(pred_data, ref_data, roi)

Authors: Boyi Du <boyi.du@uq.net.au>, Ashley Stewart <ashley.stewart@uq.edu.au>

"""

import json
import argparse
import os
import numpy as np
import csv
import nibabel as nib

from sklearn.metrics import mean_squared_error
from skimage.metrics import structural_similarity
from skimage.metrics import normalized_mutual_information
from skimage.measure import pearson_corr_coeff
from scipy.ndimage import gaussian_laplace

def calculate_rmse(pred_data, ref_data):
    """
    Calculate the Root Mean Square Error (RMSE) between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.

    Returns
    -------
    float
        The calculated RMSE value.

    """
    mse = mean_squared_error(pred_data, ref_data)
    rmse = np.sqrt(mse)
    return rmse

def calculate_nrmse(pred_data, ref_data):
    """
    Calculate the Normalized Root Mean Square Error (NRMSE) between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.

    Returns
    -------
    float
        The calculated NRMSE value.

    References
    ----------
    .. [1] https://github.com/scikit-image/scikit-image/blob/v0.21.0/skimage/metrics/simple_metrics.py#L50-L108
    """
    rmse = calculate_rmse(pred_data, ref_data)
    nrmse = rmse * np.sqrt(len(ref_data)) / np.linalg.norm(ref_data) * 100 # Frobenius norm
    return nrmse

def calculate_hfen(pred_data, ref_data):
    """
    Calculate the High Frequency Error Norm (HFEN) between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.

    Returns
    -------
    float
        The calculated HFEN value.
    References
    ----------
    .. [1] https://doi.org/10.1002/mrm.26830

    """
    LoG_pred = gaussian_laplace(pred_data, sigma = 1.5)
    LoG_ref = gaussian_laplace(ref_data, sigma = 1.5)
    hfen = np.linalg.norm(LoG_ref - LoG_pred)/np.linalg.norm(LoG_ref)
    return hfen

def calculate_xsim(pred_data, ref_data, data_range=None):
    """
    Calculate the structural similarity (XSIM) between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.
    data_range : float
        Expected data range.

    Returns
    -------
    float
        The calculated structural similarity value.

    References
    ----------
    .. [1] Milovic, C., et al. (2024). XSIM: A structural similarity index measure optimized for MRI QSM. Magnetic Resonance in Medicine. doi:10.1002/mrm.30271
    """
    if not data_range: data_range = ref_data.max() - ref_data.min()
    xsim = structural_similarity(pred_data, ref_data, win_size=3, K1=0.01, K2=0.001, data_range=data_range)
    return xsim

def calculate_mad(pred_data, ref_data):
    """
    Calculate the Mean Absolute Difference (MAD) between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.

    Returns
    -------
    float
        The calculated MAD value.

    """
    mad = np.mean(np.abs(pred_data - ref_data))
    return mad

def calculate_gxe(pred_data, ref_data):
    """
    Calculate the gradient difference error (GXE) between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.

    Returns
    -------
    float
        The calculated GXE value.

    """
    gxe = np.sqrt(np.mean((np.array(np.gradient(pred_data)) - np.array(np.gradient(ref_data))) ** 2))
    return gxe


def get_bounding_box(roi):
    """
    Calculate the bounding box of a 3D region of interest (ROI).

    Parameters
    ----------
    roi : numpy.ndarray
        A 3D numpy array representing a binary mask of the ROI,
        where 1 indicates an object of interest and 0 elsewhere.

    Returns
    -------
    bbox : tuple
        A tuple of slice objects representing the bounding box of the ROI. This can be 
        directly used to slice numpy arrays.

    Example
    -------
    >>> mask = np.random.randint(0, 2, size=(100, 100, 100))
    >>> bbox = get_bounding_box(mask)
    >>> sliced_data = data[bbox]

    Notes
    -----
    The function works by identifying the min and max coordinates of the ROI along 
    each axis. These values are used to generate a tuple of slice objects.
    The function will work for ROIs of arbitrary dimension, not just 3D.
    """
    coords = np.array(roi.nonzero())
    min_coords = coords.min(axis=1)
    max_coords = coords.max(axis=1) + 1
    return tuple(slice(min_coords[d], max_coords[d]) for d in range(roi.ndim))


def all_metrics(pred_data, ref_data, roi=None):
    """
    Calculate various error metrics between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.
    roi : numpy.ndarray, optional
        A binary mask defining a region of interest within the data. If not provided,
        the full extent of pred_data and ref_data is used.

    Returns
    -------
    dict
        A dictionary of calculated error metrics, including RMSE, NRMSE, HFEN, XSIM, MAD, 
        CC (Pearson Correlation Coefficient), NMI (Normalized Mutual Information) and GXE 
        (Gradient difference error).

    """
    d = dict()

    if roi is None:
        roi = np.array(pred_data != 0, dtype=bool)

    bbox = get_bounding_box(roi)
    pred_data = pred_data[bbox]
    ref_data = ref_data[bbox]
    roi = roi[bbox]

    if np.isnan(pred_data).any() or np.isnan(ref_data).any():
        print("[WARNING] Input arrays contain NaN values.")
    if np.std(pred_data) == 0:
        print("[WARNING] The predicted data has no variance.")
    if np.std(ref_data) == 0:
        print("[WARNING] The reference data has no variance.")

    d['RMSE'] = calculate_rmse(pred_data[roi], ref_data[roi])
    d['NRMSE'] = calculate_nrmse(pred_data[roi], ref_data[roi])
    d['HFEN'] = calculate_hfen(pred_data, ref_data)  # does not flatten
    d['MAD'] = calculate_mad(pred_data[roi], ref_data[roi])
    d['XSIM'] = calculate_xsim(pred_data, ref_data)  # does not flatten
    d['CC'] = pearson_corr_coeff(pred_data[roi], ref_data[roi])
    d['NMI'] = normalized_mutual_information(pred_data[roi], ref_data[roi])
    d['GXE'] = calculate_gxe(pred_data, ref_data)  # does not flatten

    return d

def save_as_csv(metrics_dict, filepath):
    """
    Save the metrics as a CSV file.

    Parameters
    ----------
    metrics_dict : dict
        A dictionary containing the metrics.
    filepath : str
        The path to the file to save the results.
    """
    with open(filepath, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Region", "Metric", "Value"])
        for region, metrics in metrics_dict.items():
            for key, value in metrics.items():
                writer.writerow([region, key, value])

def save_as_markdown(metrics_dict, filepath):
    """
    Save the metrics as a markdown table.

    Parameters
    ----------
    metrics_dict : dict
        A dictionary containing the metrics.
    filepath : str
        The path to the file to save the results.
    """
    with open(filepath, 'w') as file:
        file.write("| Metric | Value |\n")
        file.write("|--------|-------|\n")
        for key, value in metrics_dict.items():
            if isinstance(value, tuple) and len(value) == 2:  # Assuming it's the PearsonRResult
                file.write(f"| {key} correlation | {value[0]:.6f} |\n")
                file.write(f"| {key} p-value | {value[1]:.6f} |\n")
            else:
                file.write(f"| {key} | {value:.6f} |\n")

def save_as_json(metrics_dict, filepath):
    """
    Save the metrics as a JSON file.

    Parameters
    ----------
    metrics_dict : dict
        A dictionary containing the metrics.
    filepath : str
        The path to the file to save the results.
    """
    with open(filepath, 'w') as file:
        json.dump(metrics_dict, file, indent=4)


def main():
    parser = argparse.ArgumentParser(description='Compute metrics for 3D images.')
    parser.add_argument('--ground_truth', type=str, help='Path to the ground truth NIFTI image.')
    parser.add_argument('--estimate', type=str, help='Path to the reconstructed NIFTI image.')
    parser.add_argument('--roi', type=str, help='Path to the ROI NIFTI image (optional).', default=None)
    parser.add_argument('--output_dir', type=str, default='./', help='Directory to save metrics.')
    parser.add_argument('--acq', type=str, help='Acquisition name (e.g., 1p0mm, 2p0mm)', default=None)
    args = parser.parse_args()

    # Load images
    print("[INFO] Loading images to compute metrics...")
    gt_img = nib.load(args.ground_truth).get_fdata()
    recon_img = nib.load(args.estimate).get_fdata()

    # Handle ROI: if not provided or file doesn't exist, use full volume
    if args.roi and os.path.exists(args.roi):
        print(f"[INFO] Using ROI file: {args.roi}")
        roi_img = np.array(nib.load(args.roi).get_fdata(), dtype=int)
        use_rois = True
    else:
        if args.roi:
            print(f"[WARNING] ROI file not found: {args.roi}")
        print("[INFO] No ROI provided - computing metrics on full brain mask")
        roi_img = np.ones_like(gt_img, dtype=int)
        use_rois = False

    print("[INFO] Computing metrics per ROI...")

    label_dict = {
        1: "Caudate",
        2: "Globus pallidus",
        3: "Putamen",
        4: "Red nucleus",
        5: "Dentate nucleus",
        6: "Substantia nigra & STN",
        7: "Thalamus",
        8: "White matter",
        9: "Gray matter",
        10: "CSF",
        11: "Blood",
        12: "Fat",
        13: "Bone",
        14: "Air",
        15: "Muscle",
        16: "Calcification"
    }

    results = {}
    
    if use_rois:
        # Process each ROI label separately
        labels = np.unique(roi_img)
        labels = labels[labels != 0]
        
        for lbl in labels:
            roi_mask = roi_img == lbl
            name = label_dict.get(lbl, f"ROI_{lbl}")
            print(f"[INFO] → Processing region: {name} (Label {lbl})")

            metrics = all_metrics(recon_img, gt_img, roi_mask)
            metrics["MeanChi_est"] = float(np.mean(recon_img[roi_mask]))
            metrics["MeanChi_gt"] = float(np.mean(gt_img[roi_mask]))

            if args.acq:
                metrics["acq"] = args.acq
            results[name] = metrics
    else:
        # Single whole-brain evaluation
        name = "Whole_Brain"
        print(f"[INFO] → Processing region: {name}")
        
        brain_mask = roi_img > 0
        metrics = all_metrics(recon_img, gt_img, brain_mask)
        metrics["MeanChi_est"] = float(np.mean(recon_img[brain_mask]))
        metrics["MeanChi_gt"] = float(np.mean(gt_img[brain_mask]))

        if args.acq:
            metrics["acq"] = args.acq
        results[name] = metrics

    # Save
    acq_suffix = f"_{args.acq}" if args.acq else ""
    print(f"[INFO] Saving metrics to {args.output_dir}...")
    csv_path = os.path.join(args.output_dir, f"roi_metrics{acq_suffix}.csv")
    md_path = os.path.join(args.output_dir, f"roi_metrics{acq_suffix}.md")
    json_path = os.path.join(args.output_dir, f"roi_metrics{acq_suffix}.json")

    save_as_csv(results, csv_path)
    save_as_markdown(results, md_path)
    save_as_json(results, json_path)

    print(f"[INFO] Metrics saved to {csv_path}, {md_path}, and {json_path}")
    
if __name__ == "__main__":
    main()

