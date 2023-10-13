"""
metrics.py

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

import argparse
import os
import numpy as np
import csv
import nibabel as nib
from sklearn.metrics import mean_squared_error
from skimage.metrics import structural_similarity
from skimage.metrics import normalized_mutual_information
from scipy.ndimage import gaussian_laplace
from skimage.measure import pearson_corr_coeff

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

def calculate_xsim(pred_data, ref_data):
    """
    Calculate the structural similarity (XSIM) between the predicted and reference data.

    Parameters
    ----------
    pred_data : numpy.ndarray
        Predicted data as a numpy array.
    ref_data : numpy.ndarray
        Reference data as a numpy array.

    Returns
    -------
    float
        The calculated structural similarity value.

    """
    xsim = structural_similarity(pred_data,ref_data,win_size = 3, K1 = 0.01, K2 = 0.001, data_range = 1)
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
        writer.writerow(["Metric", "Value"])
        for key, value in metrics_dict.items():
            writer.writerow([key, value])

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
            file.write(f"| {key} | {value:.6f} |\n")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Compute metrics for 3D images.')
    parser.add_argument('ground_truth', type=str, help='Path to the ground truth NIFTI image.')
    parser.add_argument('recon', type=str, help='Path to the reconstructed NIFTI image.')
    parser.add_argument('--roi', type=str, help='Path to the ROI NIFTI image (optional).')
    parser.add_argument('--output_dir', type=str, default='./', help='Directory to save metrics.')
    args = parser.parse_args()

    # Load images
    gt_img = nib.load(args.ground_truth).get_fdata()
    recon_img = nib.load(args.recon).get_fdata()

    if args.roi:
        roi_img = nib.load(args.roi).get_fdata()
    else:
        roi_img = None

    # Compute metrics
    metrics = all_metrics(recon_img, gt_img, roi_img)

    # Save metrics
    csv_path = os.path.join(args.output_dir, 'metrics.csv')
    md_path = os.path.join(args.output_dir, 'metrics.md')

    save_as_csv(metrics, csv_path)
    save_as_markdown(metrics, md_path)

    print(f"Metrics saved to {csv_path} and {md_path}")
    
