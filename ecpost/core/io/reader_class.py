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

from ecpost.core.utils.config import Config
from ecpost.core.utils import catalogue

class NemoReader:
    """
    Reader and preprocessor class for NEMO ocean/ice model output.
    """

    def __init__(self, config_path: str = None):
        """
        Initialize the NemoReader with an optional configuration path.

        Args:
            config_path : str, optional
                Path to the configuration file.
        """
    
        self.config_path = config_path
        self.config = Config(config_path=config_path)

    @staticmethod
    def detect_axis(ds, axis_type, component='nemo', where='dims', verbose=False):
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

        # get candidate's list from catalogue
        candidates_dict = catalogue.axis_candidates(component)
        candidates = candidates_dict.get(axis_type, [])

        if where in ['dims', 'coords']:
            search_space = getattr(ds, where, {})
        else:
            search_space = ds.data_vars

        for candidate in candidates:
            if candidate in search_space:
                if verbose:
                    print(f"Found {axis_type} axis: '{candidate}' in {where}")
                return candidate

        return None


    def nemodict(self, grid, freq):
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
                    "preproc": self.preproc_nemo,
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
            return {
                "W": {
                    "preproc": self.preproc_nemo,
                    "format": f"oce_{freq}_{grid}",
                    "nav_lat": ["nav_lat", "lat"],
                    "nav_lon": ["nav_lon", "lon"],
                    "depth": [f"depth{grid_lower}", "z"]
                }
            }
        elif grid_lower == "ice":
            return {
                "ice": {
                    "preproc": self.preproc_nemo_ice,
                    "format": f"ice_{freq}"
                }
            }
        else:
            raise ValueError(f"Unsupported grid type: {grid}")


    def preproc_nemo(self, data):
        """
        General preprocessing routine for NEMO data.
        Remove spurious dimensions/coordinates/variables and standardize axes.

        """

        axis_map = {}
        for ax in ['time', 'x', 'y', 'z']:
            name = self.detect_axis(data, ax, where='dims')
            if name:
                axis_map[name] = ax

        for ax in ['lon', 'lat']:
            name = self.detect_axis(data, ax, where='coords')
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


    def preproc_nemo_ice(self, data):
        """Preprocessing routine for NEMO for ice"""

        axis_map = {}
        for ax in ['time', 'x', 'y', 'ncatice']:
            name = self.detect_axis(data, ax, where='dims')
            if name:
                axis_map[name] = ax

        for ax in ['lon', 'lat']:
            name = self.detect_axis(data, ax, where='coords')
            if name:
                axis_map[name] = ax
        
        if axis_map:
            data = data.rename(axis_map)

        if "axis_nbounds" in data.dims:
            data = data.drop_dims(["axis_nbounds"])

        if "time_centered" in data.coords:
            data = data.drop_vars(["time_centered"])            

        if "time_centered_bounds" in data.data_vars:
            data = data.drop_vars(["time_centered_bounds"])

        if "time_counter_bounds" in data.data_vars:
            data = data.drop_vars(["time_counter_bounds"])

        return data


    def reader_nemo(self, expname, startyear, endyear, grid="T", freq="1m"):
        """ 
        reader_nemo: function to read NEMO data 
        
        Args:
        expname: experiment name
        startyear,endyear: time window
        grid: grid name [T, U, V, W]
        frequency: output frequency [1m, 1y, ...]

        """

        logging.info(f"Loading experiment: {expname}, grid: {grid}, range: ({startyear}-{endyear})")

        # load folders
        dirs = self.config.folders(expname)

        # dictionary of NEMO output features
        dict = self.nemodict(grid, freq)

        # search pattern
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

        logging.debug('Loading files: %s', filelist)
        time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
        data = xr.open_mfdataset(filelist, preprocess=lambda d: dict[grid]["preproc"](d), decode_times=time_coder, data_vars="all")

        return data


    def reader_nemo_field(self, expname, startyear, endyear, varname, freq="1m"):
        """ 
        reader_nemo_field: function to read NEMO field 
        
        Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name

        """

        logging.info(f"Reading NEMO field: {varname}")

        info = catalogue.observables('nemo')[varname]

        # Check for 'dependencies' if dealing with derived variable 
        if 'dependencies' in info: 
            field = {}
            for grid, var in zip(info['grid'], info['dependencies']):
                data = self.reader_nemo(expname=expname, startyear=startyear, endyear=endyear, grid=grid)
                field[var] = data[var]
                if 'preprocessing' in info and var in info['preprocessing']:
                    field[var] = info['preprocessing'][var](field[var])
            data = info['operation'](*[field[var] for var in info['dependencies']])
        else:
            data = self.reader_nemo(expname=expname, startyear=startyear, endyear=endyear, grid=info['grid'], freq=freq)
            data = data[[varname]]

        return data


