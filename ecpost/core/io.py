#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
I/O module

Author: Alessandro Sozza (CNR-ISAC)
Date: Nov 2025
"""

import os
import glob
import shutil
import subprocess
import logging
import xarray as xr
import cftime
import dask

from ecpost.core import config
from ecpost.core import catalogue

# dask optimization
#dask.config.set({'array.optimize_blockwise': True})

##########################################################################################
# Detector of axis candidates

axis_candidates = {
    'time': ['time_counter', 'time', 't'],
    'x': ['x', 'x_grid_T', 'x_grid_U', 'x_grid_V', 'x_grid_W', 'lon', 'longitude', 'nav_lon'],
    'y': ['y', 'y_grid_T', 'y_grid_U', 'y_grid_V', 'y_grid_W', 'lat', 'latitude', 'nav_lat'],
    'z': ['deptht', 'depthu', 'depthv', 'depthw', 'depth', 'z', 'lev', 'nav_lev']
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
                "preproc": preproc_nemo_new,
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
                "preproc": preproc_nemo_new,
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


def preproc_nemo_new(ds, grid):
    """Preprocessing NEMO: rimuove dimensioni spurie e uniforma gli assi."""
    # Rimuove dimensioni di lunghezza 1
    ds = ds.squeeze(drop=True)
    if "iax_20C" in ds.coords:
        ds = ds.drop_vars("iax_20C")

    # Trova gli assi
    axis_map = {}
    for ax in ['time', 'x', 'y', 'z']:
        name = detect_axis(ds, ax, where='dims')
        if name:
            axis_map[name] = ax

    # Rinomina in modo coerente
    if axis_map:
        ds = ds.rename(axis_map)

    return ds


def preproc_nemo(data, grid):
    """ 
    General preprocessing routine for NEMO data based on grid type
    
    Args: 
    data: dataset
    grid: gridname [T, U, V, W]

    """
    
    grid_mappings = _nemodict(grid, None)[grid]  # None for freq as it is not used here

    if grid != 'W':
        data = data.rename_dims({grid_mappings["x_grid"]: 'x', grid_mappings["y_grid"]: 'y'})
        data = data.swap_dims({grid_mappings["x_grid_inner"]: 'x', grid_mappings["y_grid_inner"]: 'y'})

    data = data.rename({
        grid_mappings["nav_lat"]: 'lat', 
        grid_mappings["nav_lon"]: 'lon', 
        grid_mappings["depth"]: 'z', 
        'time_counter': 'time'
    })

    # Drop spurious dimensions and variables
    data = data.drop_vars(['time_centered'], errors='ignore')
    data = data.drop_dims(['axis_nbounds'], errors='ignore')
    if grid == 'T':
        data = data.drop_dims(['iax_20C'], errors='ignore')

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
    data = xr.open_mfdataset(filelist, preprocess=lambda d: dict[grid]["preproc"](d, grid), decode_times=time_coder, data_vars="all") #, chunks={'time_counter': 12})

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
# Rebuilder

def _get_nemo_timestep(filename):
    """ Get timestep from a NEMO restart file """

    return os.path.basename(filename).split('_')[1]

def rebuilder(expname, leg):
    """Function to rebuild NEMO restart """

    dirs = config.folders(expname)
    
    os.makedirs(os.path.join(dirs['tmp'], str(leg).zfill(3)), exist_ok=True)

    rebuild_exe = os.path.join(dirs['rebuild'], "rebuild_nemo")
  
    for kind in ['restart', 'restart_ice']:
        print(' Processing ' + kind)
        flist = glob.glob(os.path.join(dirs['restart'], str(leg).zfill(3), expname + '*_' + kind + '_????.nc'))
        tstep = _get_nemo_timestep(flist[0])

        for filename in flist:
            destination_path = os.path.join(dirs['tmp'], str(leg).zfill(3), os.path.basename(filename))
            try:
                os.symlink(filename, destination_path)
            except FileExistsError:
                pass

        rebuild_command = [rebuild_exe, "-m", os.path.join(dirs['tmp'], str(leg).zfill(3), expname + "_" + tstep + "_" + kind ), str(len(flist))]
        try:
            print(rebuild_command)
            subprocess.run(rebuild_command, stderr=subprocess.PIPE, text=True, check=True)
            for file in glob.glob('nam_rebuld_*'):
                os.remove(file)
        except subprocess.CalledProcessError as e:
            error_message = e.stderr
            print(error_message)

        for filename in flist:
            destination_path = os.path.join(dirs['tmp'], str(leg).zfill(3), os.path.basename(filename))
            os.remove(destination_path)

    # copy restart
    tstep = _get_nemo_timestep(glob.glob(os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '*_restart.nc'))[0])
    shutil.copy(os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '_' + tstep + '_restart.nc'), os.path.join(dirs['tmp'], str(leg).zfill(3), 'restart.nc'))
    shutil.copy(os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '_' + tstep + '_restart_ice.nc'), os.path.join(dirs['tmp'], str(leg).zfill(3), 'restart_ice.nc'))

    # delete temporary files
    flist = glob.glob('nam_rebuild*')
    for file in flist:
        os.remove(file)

    return None

##########################################################################################
# Reader of NEMO restart (rebuilt)

def reader_rebuilt(expname, startleg, endleg):
    """
    Read rebuilt NEMO restart files using a list of candidate patterns.

    Parameters:
        expname (str): Nome dell'esperimento.
        startleg (int): Numero del leg iniziale.
        endleg (int): Numero del leg finale.
                                          
    Returns:
        xarray.Dataset: Dataset unito dai file trovati.
    """

    dirs = config.folders(expname)
    filelist = []

    # Default patterns
    candidate_patterns = [
        "{expname}*_restart.nc",
        "restart.nc"
    ]

    for leg in range(startleg, endleg + 1):
        for pat in candidate_patterns:            
            pattern_str = pat.format(expname=expname)
            full_pattern = os.path.join(dirs['tmp'], str(leg).zfill(3), pattern_str)
            matching_files = glob.glob(full_pattern)
            filelist.extend(matching_files)

    if not filelist:
        logging.warning("No file found")
    else:
        logging.info("Loading File: %s", filelist)

    data = xr.open_mfdataset(filelist, use_cftime=True, engine="netcdf4") if filelist else None

    return data

def _get_leg(year, year_zero=1990):
    """ Get leg from date """

    return (year - year_zero + 1)

# Reader of multiple restarts (rebuilt or not)
def reader_restarts(expname, startyear, endyear):
    """ 
    reader_restart: reader of NEMO restart files in a range of legs 
    
    Args:
    expname: experiment name
    startyear,endyear: time window

    """

    startleg = _get_leg(startyear)
    endleg = _get_leg(endyear)

    try:
        data = reader_rebuilt(expname, startleg, endleg)
        return data
    except FileNotFoundError:
        print(" Restart file not found. Rebuilding ... ")

    # rebuild files
    for leg in range(startleg,endleg+1):
        rebuilder(expname, leg)

    data = reader_rebuilt(expname, startleg, endleg)

    return data

##########################################################################################
