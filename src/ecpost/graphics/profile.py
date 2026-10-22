#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graphics for profiles

Author: Alessandro Sozza (CNR-ISAC) 
Date: Mar 2024
"""

import os
import numpy as np
import xarray as xr
import cftime
#import nc_time_axis
import matplotlib.pyplot as plt

from ecpost.utils import catalogue
from ecpost.io.reader import reader_nemo_field
from ecpost.io.postreader import averaging, get_profile
from ecpost.means.means import timemean


def _rescaled(vec):
    """ rescale by the initial value """
    return vec/vec[0]

def _read_profile(expname, startyear, endyear, varname, reader="post", orca="ORCA2", replace=False):
    """ Vertical profile (horizontal mean averaged over the window) from raw data ('nemo') or from the 'hovmoller' diagnostic ('post') """

    # Read data from raw NEMO output
    if reader == 'nemo':
        data = reader_nemo_field(expname=expname, startyear=startyear, endyear=endyear, varname=varname)
        data = averaging(data=data, varname=varname, diagname='hovmoller', orca=orca)
        data = timemean(data=data, mode='global')

    # Read data from post-processed data
    elif reader == 'post':
        data = get_profile(expname=expname, startyear=startyear, endyear=endyear, varname=varname,
                           mode='global', orca=orca, replace=replace)

    else:
        raise ValueError(f"Unknown reader '{reader}'. Choose between 'nemo' and 'post'")

    return data

def plot_profile(expname, startyear, endyear, varname, 
            reader="post", orca="ORCA2", replace=False,
            color=None, linestyle='-', marker=None, label=None, ax=None, figname=None):
    """ 
    Graphics of vertical profile (horizontal mean) averaged over the time window
    
    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varname: variable name (3D)

    Optional Args:
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - replace: replace existing files [False or True]
    
    Optional Args for figure settings:
    - color, linestyle, marker, label: plot attributes
    - figname: save plot to file

    """

    info = catalogue.observables('nemo')[varname]

    data = _read_profile(expname, startyear, endyear, varname, reader=reader, orca=orca, replace=replace)
    vec = data[varname].values.flatten()

    # fixing depth y-axis
    zvec = data['z'].values.flatten()

    # load plot features
    plot_kwargs = {}
    if color:
        plot_kwargs['color'] = color
    if linestyle:
        plot_kwargs['linestyle'] = linestyle
    if marker:
        plot_kwargs['marker'] = marker
    if label:
        plot_kwargs['label'] = label

    # plot profile
    pp = plt.plot(vec, -zvec, **plot_kwargs)
    plt.xlabel(info['long_name'])
    plt.ylabel('depth')

    # Save figure
    if figname:
        plt.savefig(figname)

    return pp

def plot_profile_diff(expname1, startyear1, endyear1, expname2, startyear2, endyear2, varname, 
            reader="post", orca="ORCA2", replace=False,
            color=None, linestyle='-', marker=None, label=None, ax=None, figname=None):
    """ 
    Graphics of the difference of vertical profiles (exp2 - exp1) averaged over the time windows
    
    Positional Args:
    - expname1,2: experiment names
    - startyear1,2, endyear1,2: time windows
    - varname: variable name (3D)

    Optional Args:
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - replace: replace existing files [False or True]
    
    Optional Args for figure settings:
    - color, linestyle, marker, label: plot attributes
    - figname: save plot to file

    """

    info = catalogue.observables('nemo')[varname]

    data1 = _read_profile(expname1, startyear1, endyear1, varname, reader=reader, orca=orca, replace=replace)
    data2 = _read_profile(expname2, startyear2, endyear2, varname, reader=reader, orca=orca, replace=replace)
    diff = data2[varname] - data1[varname]
    vec = diff.values.flatten()

    # fixing depth y-axis
    zvec = data1['z'].values.flatten()

    # load plot features
    plot_kwargs = {}
    if color:
        plot_kwargs['color'] = color
    if linestyle:
        plot_kwargs['linestyle'] = linestyle
    if marker:
        plot_kwargs['marker'] = marker
    if label:
        plot_kwargs['label'] = label

    # plot profile
    pp = plt.plot(vec, -zvec, **plot_kwargs)
    plt.xlabel(f"{info['long_name']} Difference [{info['units']}]")
    plt.ylabel('Depth [m]')

    # Save figure
    if figname:
        plt.savefig(figname)

    return pp