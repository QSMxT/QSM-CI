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

Author: Boyi Du <boyi.du@uq.net.au>

"""

import numpy as np
from sklearn.metrics import mean_squared_error
from skimage.metrics import structural_similarity
from skimage.metrics import normalized_mutual_information
from scipy.ndimage import gaussian_laplace
from numpy.linalg import norm
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

    """
    rmse = calculate_rmse(pred_data, ref_data)
    nrmse = rmse / np.linalg.norm(pred_data) * 100
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

    """
    LoG_pred = gaussian_laplace(pred_data, sigma = 1.5)
    LoG_ref = gaussian_laplace(ref_data, sigma = 1.5)
    hfen = norm(LoG_ref - LoG_pred)/norm(LoG_pred)
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
        A dictionary of calculated error metrics, including RMSE, NRMSE, FHEN, XSIM, MAD, 
        CC (Pearson Correlation Coefficient), NMI (Normalized Mutual Information) and GXE 
        (Gradient difference error).

    """
    d = dict()

    if roi is not None:
        roi = np.array(roi, dtype=bool)
        bbox = get_bounding_box(roi)
        pred_data = pred_data[bbox]
        ref_data = ref_data[bbox]
        roi = roi[bbox]
    else:
        roi = np.ones(pred_data.shape, dtype=bool)

    d['RMSE'] = calculate_rmse(pred_data[roi], ref_data[roi])
    d['NRMSE'] = calculate_nrmse(pred_data[roi], ref_data[roi])
    d['FHEN'] = calculate_hfen(pred_data, ref_data)  # does not flatten
    d['MAD'] = calculate_mad(pred_data[roi], ref_data[roi])
    d['XSIM'] = calculate_xsim(pred_data, ref_data)  # does not flatten
    d['CC'] = pearson_corr_coeff(pred_data[roi], ref_data[roi])
    d['NMI'] = normalized_mutual_information(pred_data[roi], ref_data[roi])
    d['GXE'] = calculate_gxe(pred_data, ref_data)  # does not flatten

    return d

