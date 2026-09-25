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

from cauda.utils import catalogue
from cauda.actions.reader import reader_nemo_field
from cauda.actions.postreader import postreader_nemo, averaging
from cauda.utils.time import get_decimal_year
from cauda.means.means import apply_cost_function, movave


def _cutted(data):
    """ Cut the first and last 6 points along the 'time' dimension for xarray objects. """
    if 'time' not in data.dims:
        raise ValueError("The input data does not have a 'time' dimension.")
    return data.isel(time=slice(6, -6))

def _rescaled(vec):
    """ rescale by the initial value """
    return vec/vec.isel(time=0)

# ISSUE: si potrebbe aggiungere un smoothing filter

def plot_hovmoller(expname, startyear, endyear, varlabel, 
               mode="plain", reader="post", orca="ORCA2", replace=False, metric="base", refinfo=None, 
               rescale=False, avetype="standard", timeoff=0, ax=None, figname=None):
    """ 
    Plot of Hovmöller diagram 
    
    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varlabel: variable name + ztag

    Optional Args:
    - mode: time mode [plain, global, yearly, monthly, seasonally, seasons, winter, sprint, summer, autumn] 
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1 ...]    
    - replace: replace existing files [False or True]
    - metric: choose the type of cost function ['base', 'norm', 'diff' ...]
    - refinfo: reference state inmodeion {expname, startyear, endyear, diagname, mode}

    Optional Args for figure settings:
    - rescale: rescale by initial value
    - avetype: moving or standard average
    - timeoff: time offset
    - ax: for drawing multiple subplots within the same figure
    - figname: save plot to file
    
    """
    
    if '-' in varlabel:
        varname, ztag = varlabel.split('-', 1)
    else:
        varname, ztag = varlabel, None

    info = catalogue.observables('nemo')[varname]

    # Read data from raw NEMO output
    if reader == "nemo":

        data = reader_nemo_field(expname=expname, startyear=startyear, endyear=endyear, varname=varname)        
        data = averaging(data=data, varlabel=varlabel, diagname='hovmoller', mode=mode, orca=orca)
        tvec = get_decimal_year(data['time'].values)

        # apply cost function
        if metric != 'base':

            xdata = reader_nemo_field(expname=refinfo['expname'], startyear=refinfo['startyear'], endyear=refinfo['endyear'], varname=varname)
            xdata = averaging(data=xdata, varlabel=varlabel, diagname=refinfo['diagname'], mode=refinfo['mode'], orca=orca)            

            if refinfo['diagname'] == 'field':
                data = apply_cost_function(data, xdata, metric, mode=mode, mode_ref=refinfo['mode'])    
                data = averaging(data=data, varlabel=varlabel, diagname='timeseries', mode=mode, orca=orca)
            else:
                data = apply_cost_function(data, xdata, metric, mode=mode, mode_ref=refinfo['mode'])


    # Read post-processed data
    elif reader == "post":

        data = postreader_nemo(expname=expname, startyear=startyear, endyear=endyear, varlabel=varlabel, 
                               diagname='hovmoller', mode=mode, orca=orca, replace=replace, metric=metric, refinfo=refinfo)
        data = data[varname]
        #tvec = get_decimal_year(data['time'].values)

    # apply rescaling
    if rescale:
        data = _rescaled(data)
    
    # plot
    pp = data.plot(x='time', y='z', cmap=plt.cm.coolwarm)
    plt.xlabel('time')
    plt.ylabel('depth')
    plt.ylim(0,5000)
    plt.gca().invert_yaxis() # invert y-axis

    return pp

