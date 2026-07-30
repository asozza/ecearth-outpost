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
import logging
import netCDF4 as nc
import xarray as xr

from ecpost.core.utils.config import Config

cfg = Config()

##########################################################################################

def _get_nemo_timestep(filename):
    """ Get timestep from a NEMO restart file """

    return os.path.basename(filename).split('_')[1]

def _delete_attrs(file):
    # Open the dataset in 'r+' mode to allow modifications
    with nc.Dataset(file, 'r+') as dataset:
        # Iterate over all variables in the dataset
        for var_name, variable in dataset.variables.items():
            # Get all attribute names for the variable
            attr_names = list(variable.ncattrs())
            # Delete each attribute
            for attr in attr_names:
                variable.delncattr(attr)  # Correct method to delete an attribute

    return None

##########################################################################################
# I/O operations on NEMO restarts

def reader_nemo_restart(expname, leg):
    """ 
    reader_nemo_restart: reader of NEMO restart files for a given leg
    
    Args:
    expname: experiment name
    leg: time leg
    """

    dirs = cfg.folders(expname)
    
    flist = glob.glob(os.path.join(dirs['restart'], str(leg).zfill(3), expname + '*_' + 'restart' + '_????.nc'))        
    tstep = _get_nemo_timestep(flist[0])

    try:
        filename = os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '_' + tstep + '_restart.nc')
        time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
        data = xr.open_mfdataset(filename, decode_times=time_coder)
        return data
    except FileNotFoundError:
        logging.info(" Restart file not found... ")

    return data


def writer_nemo_restart(data, expname, leg):
    """ 
    writer_nemo_restart: writer of NEMO restart files for a given leg in a temporary folder
    
    Args:
    expname: experiment name
    leg: time leg
    """

    dirs = cfg.folders(expname)
    flist = glob.glob(os.path.join(dirs['restart'], str(leg).zfill(3), expname + '*_' + 'restart' + '_????.nc'))
    timestep = _get_nemo_timestep(flist[0])

    # ocean restart creation
    filename = os.path.join(dirs['tmp'], str(leg).zfill(3), 'restart.nc')
    data.to_netcdf(filename, mode='w', unlimited_dims={'time_counter': True})

    # delete attributes
    _delete_attrs(filename)

    # copy ice restart
    inifile = os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '_' + timestep + '_restart_ice.nc')
    outfile = os.path.join(dirs['tmp'], str(leg).zfill(3), 'restart_ice.nc')
    shutil.copy(inifile, outfile)

    return None


def update_nemo_restart(expname, leg, use_symlinks=False):
    """
    Replace modified NEMO restart files in the run execution folder.
    
    Args:
        exp_name (str): Name of the experiment.
        leg_number (int): Current simulation leg/segment number.
        use_symlinks (bool): If True, links files from the restart archive. 
                             If False, copies them directly to the run folder.
    """
    
    dirs = cfg.folders(expname)
    
    # Paths definition
    run_dir = dirs['exp']
    restart_store = dirs['restart']
    temp_dir = dirs['tmp']
    
    # Format leg number (e.g., 1 -> '001')
    leg_id = str(leg).zfill(3)
    restart_files = ['restart.nc', 'restart_ice.nc']

    # 1. Cleaning: Remove old restart files in the run directory
    # Find all files matching 'restart*.nc' in the run directory
    search_pattern = os.path.join(dirs['exp'], 'restart*.nc')
    for old_file in glob.glob(search_pattern):
        if os.path.isfile(old_file):
            print(f"Removing {old_file}")
            os.remove(old_file)

    # 2. Deliver new files
    for filename in restart_files:
        # Define source and destination paths
        source_temp = os.path.join(dirs['tmp'], leg_id, filename)
        target_archive = os.path.join(dirs['restart'], leg_id, filename)
        run_destination = os.path.join(dirs['exp'], filename)

        # Skip if the source file doesn't exist
        if not os.path.exists(source_temp):
            print(f"Warning: {source_temp} not found, skipping.")
            continue

        if use_symlinks:
            # 1. Copy rebuilt file to the permanent restart storage
            shutil.copy(source_temp, target_archive)
            
            # 2. Create a symbolic link in the run directory
            print(f"Linking rebuilt NEMO restart: {filename}")
            if os.path.lexists(run_destination):
                os.remove(run_destination) # Ensure no stale link exists
            os.symlink(target_archive, run_destination)
        else:
            # Direct copy from temp to the run directory
            print(f"Copying {filename} to {dirs['exp']}")
            shutil.copy(source_temp, run_destination)

    return None


def restore_nemo_restart(expname, leg):
    """ Restore original nemo restart files """

    dirs = cfg.folders(expname)

    # copying from the restart folder required for the leg you asked
    browser = ['*restart*']
    for file in browser:
        filelist = sorted(glob.glob(os.path.join(dirs['restart'], str(leg).zfill(3), file)))
        for file in filelist:
            basefile = os.path.basename(file)
            targetfile = os.path.join(dirs['exp'], basefile)
            if not os.path.isfile(targetfile):
                if 'restart' in basefile:
                    newfile = os.path.join(dirs['exp'], '_'.join(basefile.split('_')[2:]))
                    print("Linking NEMO restart", file)
                    os.symlink(file, newfile)

    return None 
