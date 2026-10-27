#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graphics for Phase-space trajectory

Author: Alessandro Sozza (CNR-ISAC) 
Date: Apr 2026
"""

import os
import numpy as np
import xarray as xr
import dask
import cftime

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from ecpost.utils import catalogue

from ecpost.io.reader import reader_nemo_field
from ecpost.io.postreader import averaging, get_timeseries
from ecpost.means.means import movave

def _cutted(vec):
    """ Cut vector """
    return vec[6:-6]

def _rescaled(vec):
    """ rescale by the initial value """
    return vec/vec[0]

def _read_timeseries(expname, startyear, endyear, varname, reader="post", orca="ORCA2", replace=False, metric="base"):
    """ Monthly surface/volume mean from raw data ('nemo') or from the 'timeseries' diagnostic ('post') """

    # Read data from raw NEMO output
    if reader == "nemo":
        data = reader_nemo_field(expname=expname, startyear=startyear, endyear=endyear, varname=varname)
        data = averaging(data=data, varname=varname, diagname='timeseries', orca=orca)

    # Read post-processed data
    elif reader == "post":
        data = get_timeseries(expname=expname, startyear=startyear, endyear=endyear, varname=varname,
                              orca=orca, replace=replace, metric=metric)

    else:
        raise ValueError(f"Unknown reader '{reader}'. Choose between 'nemo' and 'post'")

    return data

def plot_trajectory(expname, startyear, endyear, varname1, varname2, 
                 reader="post", orca="ORCA2", metric="base", replace=False, rescale=False, avetype="moving", 
                 color=None, linestyle='-', marker=None, label=None, figname=None):
    """ 
    Gregory Plot

    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varname1,varname2: variable names

    Optional Args:
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - metric: choose the type of cost function ['base', 'norm', 'diff' ...] (post only)
    - replace: replace existing files [False or True]
    
    Optional Args for figure settings:
    - rescale: rescale by initial value
    - avetype: choose the type of average ['moving' or 'standard']   
    - color, linestyle, marker, label: plot attributes
    - figname: save plot to file
         
    """

    info1 = catalogue.observables('nemo')[varname1]
    info2 = catalogue.observables('nemo')[varname2]

    data1 = _read_timeseries(expname, startyear, endyear, varname1, reader=reader, orca=orca, replace=replace, metric=metric)
    data2 = _read_timeseries(expname, startyear, endyear, varname2, reader=reader, orca=orca, replace=replace, metric=metric)
    tvec = data1['time'].values.flatten()

    # apply moving average
    if avetype == 'moving':
        vec1 = movave(data1[varname1],12)
        vec2 = movave(data2[varname2],12)
        tvec, vec1, vec2 = _cutted(tvec), _cutted(vec1), _cutted(vec2)
    else:
        vec1 = data1[varname1].values.flatten()
        vec2 = data2[varname2].values.flatten()


    # markers
    years_interval = 120 # number of months x years of one chunk
    time_indices = np.arange(0, len(tvec), years_interval)    
    vec1_markers = vec1[time_indices]
    vec2_markers = vec2[time_indices]

    # plot
    plot_kwargs = {}
    if color:
        plot_kwargs['color'] = color
    if linestyle:
        plot_kwargs['linestyle'] = linestyle
    if label:
        plot_kwargs['label'] = label

    scatter_kwargs = {}
    if color:
        scatter_kwargs['color'] = color
    if marker:
        scatter_kwargs['marker'] = marker

    fig = plt.subplot()

    plt.plot(vec1, vec2, **plot_kwargs)
    plt.scatter(vec1_markers, vec2_markers, zorder=10, edgecolor='black', label='_nolegend_', **scatter_kwargs)

    # Set labels, example labels here
    plt.xlabel(info1['long_name'])
    plt.ylabel(info2['long_name'])

    # Save figure
    if figname:
        plt.savefig(figname)

    return fig


def gregory_plot_january(expname, startyear, endyear, varname1, varname2, 
                         reader="post", orca="ORCA2", metric="base", replace=False, rescale=False, avetype="moving", 
                         color=None, linestyle='-', marker=None, label=None, figname=None):
    """ 
    Gregory Plot

    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varname1,varname2: variable names

    Optional Args:
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - metric: choose the type of cost function ['base', 'norm', 'diff' ...] (post only)
    - replace: replace existing files [False or True]
    
    Optional Args for figure settings:
    - rescale: rescale by initial value
    - avetype: choose the type of average ['moving', 'standard' or 'january']   
    - color, linestyle, marker, label: plot attributes
    - figname: save plot to file
         
    """

    info1 = catalogue.observables('nemo')[varname1]
    info2 = catalogue.observables('nemo')[varname2]

    data1 = _read_timeseries(expname, startyear, endyear, varname1, reader=reader, orca=orca, replace=replace, metric=metric)
    data2 = _read_timeseries(expname, startyear, endyear, varname2, reader=reader, orca=orca, replace=replace, metric=metric)

    # apply moving average
    if avetype == 'moving':
        vec1 = _cutted(movave(data1[varname1],12))
        vec2 = _cutted(movave(data2[varname2],12))
    elif avetype == 'standard':
        vec1 = data1[varname1].values.flatten()
        vec2 = data2[varname2].values.flatten()
    elif avetype == 'january':
        vec1 = data1[varname1].sel(time=data1['time.month']==1).values.flatten()
        vec2 = data2[varname2].sel(time=data2['time.month']==1).values.flatten()

    # plot
    plot_kwargs = {}
    if color:
        plot_kwargs['color'] = color
    if linestyle:
        plot_kwargs['linestyle'] = linestyle
    if marker:
        plot_kwargs['marker'] = marker
    if label:
        plot_kwargs['label'] = label

    fig = plt.subplot()

    plt.plot(vec1, vec2, **plot_kwargs)

    # Set labels, example labels here
    plt.xlabel(info1['long_name'])
    plt.ylabel(info2['long_name'])

    # Save figure
    if figname:
        plt.savefig(figname)

    return fig

