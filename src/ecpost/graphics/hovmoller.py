#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graphics for Hovmöller diagrams 

Author: Alessandro Sozza (CNR-ISAC) 
Date: Mar 2024
"""

import os
import numpy as np
import xarray as xr
import dask
import cftime
import matplotlib.pyplot as plt

from ecpost.utils import catalogue
from ecpost.utils.time import get_decimal_year
from ecpost.io.reader import reader_nemo_field
from ecpost.io.postreader import averaging, get_hovmoller
from ecpost.means.means import apply_cost_function, timemean


def _cutted(data):
    """ Cut the first and last 6 points along the 'time' dimension for xarray objects. """
    if 'time' not in data.dims:
        raise ValueError("The input data does not have a 'time' dimension.")
    return data.isel(time=slice(6, -6))

def _rescaled(vec):
    """ rescale by the initial value """
    return vec/vec.isel({d: 0 for d in vec.dims if d in ('time', 'year')})

# ISSUE: si potrebbe aggiungere un smoothing filter

def plot_hovmoller(expname, startyear, endyear, varname, 
               mode="plain", reader="post", orca="ORCA2", replace=False, metric="base", refinfo=None, config_path=None,
               rescale=False, avetype="standard", timeoff=0, zmax=5000, ax=None, figname=None, **kwargs):
    """ 
    Plot of Hovmöller diagram 
    
    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varname: variable name (3D)

    Optional Args:
    - mode: time mean [plain, yearly] (see get_hovmoller)
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1 ...]    
    - replace: replace existing files [False or True]
    - metric: choose the type of cost function ['base', 'norm', 'diff' ...]
    - refinfo: reference climatology {expname, startyear, endyear}, required if metric != 'base'
    - config_path: configuration file

    Optional Args for figure settings:
    - rescale: rescale by initial value
    - avetype: moving or standard average
    - timeoff: time offset
    - zmax: maximum depth shown
    - ax: for drawing multiple subplots within the same figure
    - figname: save plot to file
    - kwargs: passed to pcolormesh (cmap, vmin, vmax, ...)
    
    """

    info = catalogue.observables('nemo')[varname]

    # Read data from raw NEMO output
    if reader == "nemo":

        data = reader_nemo_field(expname=expname, startyear=startyear, endyear=endyear, varname=varname)        

        # apply cost function w.r.t. the reference climatology, before any average (as in postreader)
        if metric != 'base':
            xdata = reader_nemo_field(expname=refinfo['expname'], startyear=refinfo['startyear'], endyear=refinfo['endyear'], varname=varname)
            xdata = timemean(data=xdata, mode='global')
            data = apply_cost_function(data, xdata, metric)

        data = averaging(data=data, varname=varname, diagname='hovmoller', orca=orca, config_path=config_path)
        data = timemean(data=data, mode=mode)

    # Read post-processed data
    elif reader == "post":

        data = get_hovmoller(expname=expname, startyear=startyear, endyear=endyear, varname=varname, 
                             mode=mode, orca=orca, replace=replace, metric=metric, refinfo=refinfo,
                             config_path=config_path)

    else:
        raise ValueError(f"Unknown reader '{reader}'. Choose between 'nemo' and 'post'")

    data = data[varname]
    tdim = 'year' if 'year' in data.dims else 'time'

    # apply rescaling
    if rescale:
        data = _rescaled(data)

    # time axis in decimal years
    if tdim == 'time':
        tvec = np.array(get_decimal_year(data['time'].values)) + timeoff
    else:
        tvec = data['year'].values + timeoff

    # plot (with its own colorbar when no axes are given, as the former xarray plot)
    colorbar = ax is None
    if ax is None:
        ax = plt.gca()
    kwargs.setdefault('cmap', plt.cm.coolwarm)
    pp = ax.pcolormesh(tvec, data['z'].values, data.transpose('z', tdim).values, shading='nearest', **kwargs)
    if colorbar:
        plt.colorbar(pp, ax=ax, label=f"{info['long_name']} [{info['units']}]")
    ax.set_xlabel('time [years]')
    ax.set_ylabel('depth [m]')
    ax.set_ylim(zmax, 0) # depth increasing downwards

    # Save figure
    if figname:
        plt.savefig(figname)

    return pp

