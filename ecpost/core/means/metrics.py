#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Metrics for climate simulations 

Author: Alessandro Sozza (CNR-ISAC)
Date: Mar 2026
"""

import numpy as np
import xarray as xr
import cftime
import logging
from scipy.interpolate import interp1d

from ecpost.core.io.domain import elements

# dictionary of months by seasons
season_months = {
        "DJF": [12, 1, 2], 
        "MAM": [3, 4, 5], 
        "JJA": [6, 7, 8], 
        "SON": [9, 10, 11],
        'winter': [12, 1, 2],
        'spring': [3, 4, 5],
        'summer': [6, 7, 8],
        'autumn': [9, 10, 11]
    }

#################################################################################
# TOOLS FOR THE FORECAST
#
# - cost function
# - forecast error?
# - year shifting / year gain
# - Kulback-Leibler divergence

def calculate_climate_metric(x, x0, metric, mode='local', dims=('lat', 'lon')):
    """
    Calcola metriche climatiche con supporto per calcolo locale o aggregato.
    
    Args:
        x: DataArray, campo del modello (3D: time, lat, lon).
        x0: DataArray, campo di riferimento (2D o 3D).
        metric: Nome della metrica ('diff', 'abserr', 'sqerr', 'reldiff', 'relabs', 'bias', 'mae', 'rmse', 'acc').
        mode: 'local' (restituisce mappa 3D) o 'global' (restituisce scalare pesato).
        dims: Dimensioni spaziali su cui mediare per le metriche globali.
    """
    
    # 1. Definizione Operazioni Locali (Base per tutto)
    # Usiamo una piccola costante per evitare divisioni per zero
    eps = 1e-10
    x0_safe = xr.where(x0 == 0, eps, x0)
    
    LOCAL_OPS = {
        'diff':    x - x0,
        'abserr':  np.abs(x - x0),
        'sqerr':   (x - x0)**2,
        'reldiff': (x - x0) / x0_safe,
        'relabs':  np.abs(x - x0) / np.abs(x0_safe)
    }

    # 2. Logica per le metriche Globali (non basate su LOCAL_OPS semplici)
    # Se la metrica richiesta è una di queste, gestiamo il calcolo pesato
    if mode == 'global':
        # Calcolo Pesi (cos(lat))
        weights = np.cos(np.deg2rad(x['lat']))
        
        if metric == 'bias':
            # Mean Bias Error (MBE)
            diff = x - x0
            return (diff * weights).sum(dim=dims) / weights.sum(dim=dims)
        
        elif metric == 'mae':
            # Mean Absolute Error
            abserr = np.abs(x - x0)
            return (abserr * weights).sum(dim=dims) / weights.sum(dim=dims)
        
        elif metric == 'rmse':
            # Root Mean Square Error
            sqerr = (x - x0)**2
            mse = (sqerr * weights).sum(dim=dims) / weights.sum(dim=dims)
            return np.sqrt(mse)
            
        elif metric == 'acc':
            # Anomaly Correlation Coefficient
            x_anom = x - x.mean(dim=dims)
            x0_anom = x0 - x0.mean(dim=dims)
            num = (x_anom * x0_anom * weights).sum(dim=dims)
            den = np.sqrt((x_anom**2 * weights).sum(dim=dims) * (x0_anom**2 * weights).sum(dim=dims))
            return num / den

    # 3. Logica per le metriche Locali
    if metric in LOCAL_OPS:
        return LOCAL_OPS[metric]
    
    raise ValueError(f"Metrica '{metric}' non supportata o modalità '{mode}' non valida.")


### AGGIUNGERE KL-DIVERGENCE

################################################################################################################

def year_shift(x1, y1, x2, y2, shift_threshold=20.0):
    """ 
    Compute year shift/gain between two timeseries (relative to curve 1) 
    
    Args:
    (x1,y1): coordinates of curve 1
    (x2,y2): coordinates of curve 2 (usually REF exp.)
    shift_threshold: maximum acceptable value of year shift

    """

    # Interpolate curve 2 with respect to y-values to get x2 = f(y2)
    interp_curve2_inv = interp1d(y2, x2, kind='linear', bounds_error=False, fill_value="extrapolate")
    
    # List to store the horizontal shift for each point of curve 1
    shifts = []
    
    # Calculate the shift for each point in curve 1
    for i in range(len(x1)):
        y1_point = y1[i]  # y-value of curve 1
        x1_point = x1[i]  # x-value of curve 1

        # Find the corresponding x-value on curve 2 for the same y-value
        x2_point = interp_curve2_inv(y1_point)
        
        # Calculate the horizontal shift
        shift = x2_point - x1_point
        
        # Add a condition for the maximum acceptable shift threshold
        if abs(shift) > shift_threshold:
            shift = np.nan  # Ignore shifts that are too large (set to NaN)
        
        shifts.append(shift)
    
    return np.array(shifts)


