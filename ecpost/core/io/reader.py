#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
I/O module

Author: Alessandro Sozza (CNR-ISAC)
Date: Nov 2025
"""

import os
import glob
import logging
import xarray as xr


from ecpost.core.utils import config
from ecpost.core.utils import catalogue

##########################################################################################

def _get_nemo_timestep(filename):
    """ Get timestep from a NEMO restart file """

    return os.path.basename(filename).split('_')[1]

##########################################################################################
# Detector of axis candidates

axis_candidates = {
    'time': ['time_counter', 'time', 't'],
    'x': ['x', 'x_grid_T', 'x_grid_T_inner', 'x_grid_U', 'x_grid_V', 'x_grid_W', 'lon', 'longitude', 'nav_lon'],
    'y': ['y', 'y_grid_T', 'y_grid_T_inner', 'y_grid_U', 'y_grid_V', 'y_grid_W', 'lat', 'latitude', 'nav_lat'],
    'z': ['deptht', 'depthu', 'depthv', 'depthw', 'depth', 'z', 'lev', 'nav_lev'],
    'lon': ['nav_lon_grid_T', 'nav_lon'],
    'lat': ['nav_lat_grid_T', 'nav_lat']
}

def detect_axis(ds, axis_type, where='dims', verbose=False):
    """
    Detects the name of a given axis (time/x/y/z) in an xarray Dataset or DataArray.

    Args:
        ds : xarray.Dataset or xarray.DataArray
            The object to inspect.
        axis_type : str
            One of ['time', 'x', 'y', 'z'].
        where : str
            Search in 'dims', 'coords' or 'data_vars'.
        verbose : bool
            If True, prints messages about detection.

    Returns:
        str or None : the name of the detected axis, or None if not found.
    """
    candidates = axis_candidates.get(axis_type, [])
    if where in ['dims', 'coords']:
        search_space = getattr(ds, where, {})
    else:
        search_space = ds.data_vars

    for candidate in candidates:
        if candidate in search_space:
            if verbose:
                print(f"Found {axis_type} axis: '{candidate}' in {where}")
            return candidate

    if verbose:
        print(f"No {axis_type} axis found among candidates: {candidates}")

    return None

##########################################################################################
# Readers of NEMO output

def _nemodict(grid, freq):
    """ 
    Nemodict: Dictionary of NEMO output fields
    
    Args: 
    grid: grid name [T, U, V, W]
    freq: output frequency [1m, 1y, ...]

    """

    grid = grid.upper().strip()
    grid_lower = grid.lower()

    if grid in ["T", "U", "V"]:
        return {
            grid: {
                "preproc": preproc_nemo,
                "format": f"oce_{freq}_{grid}",
                "x_grid": [f"x_grid_{grid}", "x"],
                "y_grid": [f"y_grid_{grid}", "y"],
                "depth": [f"depth{grid_lower}", "z"],
                "nav_lat": [f"nav_lat_grid_{grid}", "nav_lat", "lat"],
                "nav_lon": [f"nav_lon_grid_{grid}", "nav_lon", "lon"],
                "x_grid_inner": [f"x_grid_{grid}_inner"],
                "y_grid_inner": [f"y_grid_{grid}_inner"]
            }
        }
    elif grid == "W":
        grid_lower = grid.lower()
        return {
            "W": {
                "preproc": preproc_nemo,
                "format": f"oce_{freq}_{grid}",
                "nav_lat": ["nav_lat", "lat"],
                "nav_lon": ["nav_lon", "lon"],
                "depth": [f"depth{grid_lower}", "z"]
            }
        }
    elif grid == "ice":
        return {
            "ice": {
                "preproc": preproc_nemo_ice,
                "format": f"ice_{freq}"
            }
        }
    else:
        raise ValueError(f"Unsupported grid type: {grid}")


def preproc_nemo(data):
    """
    General preprocessing routine for NEMO data.
    Remove spurious dimensions/coordinates/variables and standardize axes.

    """

    axis_map = {}
    for ax in ['time', 'x', 'y', 'z']:
        name = detect_axis(data, ax, where='dims')
        if name:
            axis_map[name] = ax

    for ax in ['lon', 'lat']:
        name = detect_axis(data, ax, where='coords')
        if name:
            axis_map[name] = ax
    
    if axis_map:
        data = data.rename(axis_map)

    if "iax_20C" in data.coords:
        data = data.drop_vars("iax_20C")
        data = data.drop_dims("iax_20C")

    if "time_centered" in data.coords:
        data = data.drop_vars(["time_centered"])

    if "axis_nbounds" in data.dims:
        data = data.drop_dims(["axis_nbounds"])

    if "x_grid_T_inner" in data.dims:
        data = data.rename({"x_grid_T_inner": "x"})

    if "y_grid_T_inner" in data.dims:
        data = data.rename({"y_grid_T_inner": "y"})

    #data = data.squeeze(drop=True)

    return data


def preproc_nemo_ice(data):
    """Preprocessing routine for NEMO for ice"""

    data = data.rename({'time_counter': 'time'})
    
    return data


def reader_nemo(expname, startyear, endyear, grid="T", freq="1m"):
    """ 
    reader_nemo: function to read NEMO data 
    
    Args:
    expname: experiment name
    startyear,endyear: time window
    grid: grid name [T, U, V, W]
    frequency: output frequency [1m, 1y, ...]

    """

    dirs = config.folders(expname)
    dict = _nemodict(grid, freq)

    filelist = []
    available_years = []
    for year in range(startyear, endyear + 1):
        pattern = os.path.join(dirs['nemo'], f"{expname}_{dict[grid]['format']}_{year}-{year}.nc")
        matching_files = glob.glob(pattern)
        if matching_files:
            filelist.extend(matching_files)
            available_years.append(year)

    if not filelist:
        raise FileNotFoundError(f"No data files found for the specified range {startyear}-{endyear}.")

    # Log a warning if some years are missing
    if available_years:
        actual_startyear = min(available_years)
        actual_endyear = max(available_years)
        if actual_startyear > startyear or actual_endyear < endyear:
            logging.warning(f"Data available only in the range {actual_startyear}-{actual_endyear}.")
        else:
            logging.info(f"Data available in the range {startyear}-{endyear}.")
    else:
        raise FileNotFoundError("No data files found within the specified range.")

    #logging.info('Files to be loaded %s', filelist)
    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    data = xr.open_mfdataset(filelist, preprocess=lambda d: dict[grid]["preproc"](d), decode_times=time_coder, data_vars="all") #, chunks={'time_counter': 12})

    return data


def reader_nemo_field(expname, startyear, endyear, varname, freq="1m"):
    """ 
    reader_nemo_field: function to read NEMO field 
    
    Args:
    expname: experiment name
    startyear,endyear: time window
    varname: variable name

    """

    info = catalogue.observables('nemo')[varname]

    # Check for 'dependencies' if dealing with derived variable 
    if 'dependencies' in info: 
        field = {}
        for grid, var in zip(info['grid'], info['dependencies']):
            data = reader_nemo(expname=expname, startyear=startyear, endyear=endyear, grid=grid)
            field[var] = data[var]
            if 'preprocessing' in info and var in info['preprocessing']:
                field[var] = info['preprocessing'][var](field[var])
        data = info['operation'](*[field[var] for var in info['dependencies']])
    else:
        data = reader_nemo(expname=expname, startyear=startyear, endyear=endyear, grid=info['grid'], freq=freq)
        data = data[[varname]]

    return data

##########################################################################################
