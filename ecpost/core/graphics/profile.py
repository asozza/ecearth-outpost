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

from ecpost.core.utils import config
from ecpost.core.utils import catalogue
from ecpost.core.io.reader import reader_nemo
from ecpost.core.io.postreader import postreader_nemo
from ecpost.core.means.means import spacemean, timemean


def _rescaled(vec):
    """ rescale by the initial value """
    return vec/vec[0]

def profile(expname, startyear, endyear, varname, 
            reader="post", orca="ORCA2", replace=False,
            color=None, linestyle='-', marker=None, label=None, ax=None, figname=None):
    """ 
    Graphics of averaged vertical profile 
    
    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varname: variable name

    Optional Args:
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - replace: replace existing files [False or True]
    
    Optional Args for figure settings:
    - rescale: rescale by initial value
    - color, linestyle, marker, label: plot attributes
    - figname: save plot to file

    """

    info = catalogue.observables('nemo')[varname]

    # Read data from raw NEMO output
    if reader == 'nemo':
        data = reader_nemo(expname=expname, startyear=startyear, endyear=endyear)
        vec = timemean(data=data, format='global')
        vec = spacemean(data=vec, ndim='2D', orca='ORCA2')

    # Read data from post-processed data
    elif reader == 'post':
        data = postreader_nemo(expname=expname, startyear=startyear, endyear=endyear, varname=varname, 
                               diagname='profile', format='global', orca=orca, replace=replace)
        vec=data[varname].values.flatten()

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
        dirs = config.paths()
        plt.savefig(os.path.join(dirs['osprey'], figname))

    return pp
