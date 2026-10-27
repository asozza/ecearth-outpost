#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graphics for timeseries

Author: Alessandro Sozza (CNR-ISAC) 
Date: Mar 2024
"""

import os
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

from ecpost.utils import catalogue
from ecpost.utils.time import get_decimal_year

from ecpost.means.means import movave, timemean, year_shift
from ecpost.io.reader import reader_nemo_field
from ecpost.io.postreader import averaging, get_timeseries


def _cutted(vec):
    """ Cut vector """
    return vec[6:-6]

def _rescaled(vec):
    """ rescale by the initial value """
    return vec/vec[0]

def _read_timeseries(expname, startyear, endyear, varname, mode="plain", reader="post", orca="ORCA2",
                     replace=False, metric="base", refinfo=None, config_path=None):
    """ Surface/volume mean from raw data ('nemo') or from the 'timeseries' diagnostic ('post'), time-averaged by mode """

    # Read data from raw NEMO output
    if reader == "nemo":
        data = reader_nemo_field(expname=expname, startyear=startyear, endyear=endyear, varname=varname)
        data = averaging(data=data, varname=varname, diagname='timeseries', orca=orca, config_path=config_path)
        data = timemean(data=data, mode=mode)

    # Read post-processed data
    elif reader == "post":
        data = get_timeseries(expname=expname, startyear=startyear, endyear=endyear, varname=varname, mode=mode,
                              orca=orca, replace=replace, metric=metric, refinfo=refinfo, config_path=config_path)

    else:
        raise ValueError(f"Unknown reader '{reader}'. Choose between 'nemo' and 'post'")

    # groupby sorts seasons alphabetically: restore calendar order
    if 'season' in data.dims:
        data = data.reindex(season=['DJF', 'MAM', 'JJA', 'SON'])

    return data

def _timeaxis(data, timeoff=0):
    """ Time axis: decimal years for 'time', otherwise the coordinate left by the time mean (year, month, season) """
    if 'time' in data.dims:
        return np.array(get_decimal_year(data['time'].values)) + timeoff
    if 'year' in data.dims:
        return data['year'].values + timeoff
    for dim in ('month', 'season'):
        if dim in data.dims:
            return data[dim].values
    raise ValueError("No time axis left (mode='global'?)")


def plot_timeseries(expname, startyear, endyear, varname, mode="plain", 
               reader="post", orca="ORCA2", replace=False, metric="base", refinfo=None, config_path=None,
               rescale=False, avetype="standard", timeoff=-1990, 
               color=None, linestyle='-', marker=None, label=None, ax=None, figname=None):
    """ 
    Graphics of timeseries 
    
    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varname: variable name

    Optional Args for the reader:
    - mode: time mean [plain, yearly, monthly, seasonally] (see get_timeseries)
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - replace: replace existing files [False or True]
    - metric: choose the type of cost function ['base', 'norm', 'diff' ...] (post only)
    - refinfo: reference climatology {expname, startyear, endyear}, required if metric != 'base'
    - config_path: configuration file

    Optional Args for figure settings:
    - rescale: rescale by initial value
    - avetype: choose the type of average ['moving' or 'standard'], moving only with mode='plain'
    - timeoff: time offset (time and year axes only)
    - color, linestyle, marker, label: plot attributes
    - ax: plot axes
    - figname: save plot to file

    """

    info = catalogue.observables('nemo')[varname]

    data = _read_timeseries(expname, startyear, endyear, varname, mode=mode, reader=reader, orca=orca, replace=replace,
                            metric=metric, refinfo=refinfo, config_path=config_path)
    tvec = _timeaxis(data, timeoff)

    # apply moving average
    if (avetype == 'moving' and mode == 'plain'):
        vec = movave(data[varname],12)
        tvec, vec = _cutted(tvec), _cutted(vec)
    else:
        vec = data[varname].values.flatten()

    # apply rescaling
    if rescale:
        vec = _rescaled(vec)

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

    # If an axis is provided, plot on it; otherwise, plot on the default plt object
    if ax is not None:
        pp = ax.plot(tvec, vec, **plot_kwargs)
        ax.set_xlabel('time')
        ax.set_ylabel(info['long_name'])  # Use a generic label or info from your dataset
    else:
        pp = plt.plot(tvec, vec, **plot_kwargs)
        plt.xlabel('time')
        plt.ylabel(info['long_name'])

    # Save figure
    if figname:
        plt.savefig(figname)

    return pp


def plot_timeseries_yearshift(expname1, startyear1, endyear1, expname2, startyear2, endyear2, varname, shift_threshold, 
                         mode='plain', reader="post", orca="ORCA2", replace=False, avetype="standard", timeoff=-1990, 
                         color=None, linestyle='-', marker=None, label=None, ax=None, figname=None):
    """ 
    Graphics of year-shift timeseries 
    
    Positional Args:
    - expname1,2: experiment names
    - startyear,endyear: time window
    - varname: variable name

    Optional Args:
    - mode: time mean [plain, yearly] (see get_timeseries)
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - replace: replace existing files [False or True]
    
    Optional Args for figure settings:
    - avetype: choose the type of average ['moving' or 'standard']
    - timeoff: time offset    
    - color, linestyle, marker, label: plot attributes
    - ax: plot axes
    - figname: save plot to file

    """

    info = catalogue.observables('nemo')[varname]

    data1 = _read_timeseries(expname1, startyear1, endyear1, varname, mode=mode, reader=reader, orca=orca, replace=replace)
    data2 = _read_timeseries(expname2, startyear2, endyear2, varname, mode=mode, reader=reader, orca=orca, replace=replace)
    tvec1, tvec2 = _timeaxis(data1), _timeaxis(data2)

    # apply moving average
    if avetype == 'moving':
        vec1 = movave(data1[varname],12)
        tvec1, vec1 = _cutted(tvec1), _cutted(vec1)
        vec2 = movave(data2[varname],12)
        tvec2, vec2 = _cutted(tvec2), _cutted(vec2)
    else:
        vec1 = data1[varname].values
        vec2 = data2[varname].values

    # compute year-shift
    shift = year_shift(tvec1, vec1, tvec2, vec2, shift_threshold)

    # add time offset
    tvec1, tvec2 = tvec1 + timeoff, tvec2 + timeoff

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

    # If an axis is provided, plot on it; otherwise, plot on the default plt object
    if ax is not None:
        pp = ax.scatter(tvec1, shift, s=2, **plot_kwargs)
        ax.axhline(0, color='gray', linestyle='--')  # Zero reference line
        ax.set_xlabel('time [years]')
        ax.set_ylabel('year shift [years]')  # Use a generic label or info from your dataset
        ax.grid()
    else:
        pp = plt.scatter(tvec1, shift, s=2, **plot_kwargs)
        plt.axhline(0, color='gray', linestyle='--')  # Zero reference line
        plt.xlabel('time [years]')
        plt.ylabel('year shift [years]')
        plt.grid()

    # Save figure
    if figname:
        plt.savefig(figname)

    return pp


def plot_timeseries_yearshift_mean(expname1, startyear1, endyear1, expname2, startyear2, endyear2, varname, shift_threshold, 
                              reader="nemo", orca="ORCA2", replace=False, avetype="standard", timeoff=0, residue=False,
                              color=None, marker=None, label=None, ax=None, figname=None):
    """ 
    Data for timeseries mean year-shift & residue
    
    Positional Args:
    - expname1,2: experiment names
    - startyear,endyear: time window
    - varname: variable name

    Optional Args:
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - replace: replace existing files [False or True]
    
    Optional Args for figure settings:
    - avetype: choose the type of average ['moving' or 'standard']
    - timeoff: time offset    
    - color, linestyle, marker, label: plot attributes
    - ax: plot axes
    - figname: save plot to file

    """

    info = catalogue.observables('nemo')[varname]

    data1 = _read_timeseries(expname1, startyear1, endyear1, varname, reader=reader, orca=orca, replace=replace)
    data2 = _read_timeseries(expname2, startyear2, endyear2, varname, reader=reader, orca=orca, replace=replace)
    tvec1, tvec2 = _timeaxis(data1), _timeaxis(data2)

    # apply moving average
    if avetype == 'moving':
        vec1 = movave(data1[varname],12)
        tvec1, vec1 = _cutted(tvec1), _cutted(vec1)
        vec2 = movave(data2[varname],12)
        tvec2, vec2 = _cutted(tvec2), _cutted(vec2)
    else:
        vec1 = data1[varname].values.flatten()
        vec2 = data2[varname].values.flatten()

    # compute year-shift
    shift = year_shift(tvec1, vec1, tvec2, vec2, shift_threshold)

    # add time offset
    tvec1, tvec2 = tvec1 + timeoff, tvec2 + timeoff

    # chunk averaging 
    step_size = 121
    mean_shift = [np.mean(shift[i:i + step_size]) for i in range(0, len(shift), step_size)]
    mean_time = [int(np.mean(tvec1[i:i + step_size])) for i in range(0, len(tvec1), step_size)]
    linear_shift = [mean_time[i]-1995 for i in range(0, len(mean_time))]
    delta_shift = [mean_shift[i]-linear_shift[i] for i in range(0, len(mean_shift))]

    # load plot features
    plot_kwargs = {}
    if color:
        plot_kwargs['color'] = color
    if marker:
        plot_kwargs['marker'] = marker
    if label:
        plot_kwargs['label'] = label

    # If an axis is provided, plot on it; otherwise, plot on the default plt object
    if ax is not None:
        if residue is False:
            pp = ax.scatter(mean_time, mean_shift, **plot_kwargs)
        else:
            pp = ax.scatter(mean_time, delta_shift, **plot_kwargs)
        ax.axhline(0, color='gray', linestyle='--')  # Zero reference line
        ax.set_xlabel('time [years]')
        ax.set_ylabel('year shift [years]')  # Use a generic label or info from your dataset
        ax.grid()
    else:
        if residue is False:
            pp = plt.scatter(mean_time, mean_shift, **plot_kwargs)
        else:
            pp = plt.scatter(mean_time, delta_shift, **plot_kwargs)
        plt.axhline(0, color='gray', linestyle='--')  # Zero reference line
        plt.xlabel('time [years]')
        plt.ylabel('year shift [years]')
        plt.grid()

    # Save figure
    if figname:
        plt.savefig(figname)

    return pp


def plot_timeseries_with_markers(expname, startyear, endyear, varname, mode="plain", 
               reader="post", orca="ORCA2", replace=False, metric="base", refinfo=None, 
               rescale=False, avetype="standard", timeoff=0, 
               color=None, linestyle='-', marker=None, label=None, ax=None, figname=None):
    """ 
    Graphics of timeseries 
    
    Positional Args:
    - expname: experiment name
    - startyear,endyear: time window
    - varname: variable name

    Optional Args:
    - mode: time mean [plain, yearly] (see get_timeseries)
    - reader: read the original raw data or averaged data ['nemo', 'post']
    - orca: ORCA configuration [ORCA2, eORCA1]
    - replace: replace existing files [False or True]
    - metric: choose the type of cost function ['base', 'norm', 'diff' ...] (post only)
    - refinfo: reference climatology {expname, startyear, endyear}, required if metric != 'base'
    
    Optional Args for figure settings:
    - rescale: rescale by initial value
    - avetype: choose the type of average ['moving' or 'standard']
    - timeoff: time offset    
    - color, linestyle, marker, label: plot attributes
    - ax: plot axes
    - figname: save plot to file

    """

    info = catalogue.observables('nemo')[varname]

    data = _read_timeseries(expname, startyear, endyear, varname, mode=mode, reader=reader, orca=orca,
                            replace=replace, metric=metric, refinfo=refinfo)
    tvec = _timeaxis(data, timeoff)

    # apply moving average
    if avetype == 'moving':
        vec = movave(data[varname],12)
        tvec, vec = _cutted(tvec), _cutted(vec)
    else:
        vec = data[varname].values.flatten()

    # apply rescaling
    if rescale:
        vec = _rescaled(vec)

    # markers
    years_interval = 120 # number of months x years of one chunk
    time_indices = np.arange(0, len(tvec), years_interval)    
    vec1_markers = tvec[time_indices]
    vec2_markers = vec[time_indices]

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

    plt.plot(tvec, vec, **plot_kwargs)
    plt.scatter(vec1_markers, vec2_markers, zorder=10, edgecolor='black', label='_nolegend_', **scatter_kwargs)

    # Set labels, example labels here
    plt.xlabel('time')
    plt.ylabel(info['long_name'])
    
    # Save figure
    if figname:
        plt.savefig(figname)

    return fig
