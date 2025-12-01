#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
post I/O module

Author: Alessandro Sozza (CNR-ISAC)
Date: Nov 2025
"""

import os
import shutil
import logging
import numpy as np
import xarray as xr

from ecpost.core.tools import config
from ecpost.core.tools import catalogue   
from ecpost.core.io.reader import reader_nemo_field
from ecpost.core.means.means import spacemean, timemean

# dask optimization of blocksizes
#dask.config.set({'array.optimize_blockwise': True})

# dictionary of months by seasons
season_months = {"DJF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}

##########################################################################################
# I/O for averaged data

def reader_averaged(expname, startyear, endyear, varname, diagname, format):
    """ 
    Reader of averaged data 
    
    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [series, prof, hovm, map, fld, pdf]
        format: time format [plain, global, monthly, seasonally, yearly]
    
    """

    dirs = config.folders(expname)

    filename = f"{varname}_{expname}_{startyear}-{endyear}_{diagname}_{format}"
    filename = os.path.join(dirs['post'], f"{filename}.nc")

    logging.info('File to be loaded %s', filename)
    data = xr.open_dataset(filename, use_cftime=True)
    
    return data


def writer_averaged(data, expname, startyear, endyear, varname, diagname, format):
    """ 
    Writer of averaged data 
    
    Args:
        data: data array
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [series, prof, hovm, map, fld, pdf]
        format: time format [plain, global, monthly, seasonally, yearly]
    
    """

    dirs = config.folders(expname)
    filename = f"{varname}_{expname}_{startyear}-{endyear}_{diagname}_{format}"
    filename = os.path.join(dirs['post'], f"{filename}.nc")

    logging.info('File to be loaded %s', filename)
    data.to_netcdf(filename, mode='w', engine='netcdf4', format='NETCDF4')

    return None


def merge_annual_files(expname, startyear, endyear, varname, diagname, format='global'):
    """
    Merge annual files

    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [series, prof, hovm, map, fld, pdf]
        format: time format [plain, global, monthly, seasonally, yearly]
    """

    dirs = config.folders(expname)
    filelist = []

    for year in range(startyear, endyear + 1):
        f = os.path.join(dirs['post'], f"{varname}_{expname}_{year}-{year}_{diagname}_{format}.nc")
        if os.path.exists(f):
            filelist.append(f)

    if not filelist:
        raise FileNotFoundError("No annual averaged files found.")

    logging.info(f"Merging {len(filelist)} averaged annual files...")

    # Using dask -- merging might be heavy
    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    ds = xr.open_mfdataset(filelist, combine='by_coords', parallel=True, decode_times=time_coder)
    writer_averaged(data=ds, expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format)

    return ds


##########################################################################################
# averaging functions
def averaging(data, varname, diagname, format, orca):
    """ 
    Averaging: Perform different flavours of averaging 
    
    Args:
        data: data array of a single field
        varname: variable name
        diagname: diagnostics name [scalar, timeseries, profile, hovmoller, map, field, pdf?]
        format: time format [plain, global, monthly, seasonally, yearly]
        orca: ORCA configuration <ORCA2, eORCA1>
    
    """

    info = catalogue.observables('nemo')[varname]

    # scalar / single-valued
    if diagname == 'scalar' or (diagname == 'timeseries' and format == 'global'):        
        data = timemean(data=data, format='global')
        data = spacemean(data=data, ndim=info['dim'], orca=orca)

    # timeseries
    if diagname == 'timeseries' and format != 'global':
        data = timemean(data=data, format=format)
        data = spacemean(data=data, ndim=info['dim'], orca=orca)

    # vertical profile
    if (diagname == 'profile' and info['dim'] == '3D'):        
        data = timemean(data=data, format='global', use_cftime=True)
        data = spacemean(data=data, ndim='2D', orca=orca)

    # hovmoller diagram
    if (diagname == 'hovmoller' and info['dim'] == '3D'):
        if (format == 'plain' or format == 'yearly'):
            data = timemean(data=data, format=format)
            data = spacemean(data=data, ndim='2D', orca=orca)

    # 2D horizontal map 
    # ISSUE: what if format != 'global'?
    if diagname == 'map':
        data = timemean(data=data, format='global')
        if info['dim'] == '3D':
            data = spacemean(data=data, ndim='1D', orca=orca)      

    # time-averaged spatial-only field 
    if diagname == 'field':
        data = timemean(data=data, format=format)

    return data


##########################################################################################
##########################################################################################
# MAIN FUNCTION
def postreader_nemo(expname, startyear, endyear, varname, diagname, format='global', orca='ORCA2', replace=False, cleanup=False):
    """ 
    Postreader_nemo: main function for reading averaged data
    
    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [series, prof, hovm, map, fld, pdf]
        format: time format [plain, global, monthly, seasonally, yearly]
        orca: ORCA configuration [ORCA2, eORCA1]
        replace: replace existing averaged file [False or True]
    
    """

    dirs = config.folders(expname)
    info = catalogue.observables('nemo')[varname]

    # try to read averaged data
    try:
        if not replace:
            data = reader_averaged(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format)
            logging.info('Averaged data found.')
            return data 
        else:
            # When replace is True, skip checking for the file and recreate it
            raise FileNotFoundError  # Trigger the exception deliberately to skip reading of averaged file
    except FileNotFoundError:
        if replace:
            logging.info('Averaged data to be replaced. Creating new file ...')
        else:
            logging.info('Averaged data not found. Creating new file ...')

    # search for existing averaged data -- both single-year and merged data 
    

    # otherwise read original data and perform averaging
    for year in range(startyear, endyear + 1):
        logging.info(f"Processing year {year}")    
        ds = reader_nemo_field(expname=expname, startyear=year, endyear=year, varname=varname)
        data = averaging(data=ds, varname=varname, diagname=diagname, format=format, orca=orca)
        writer_averaged(data=data, expname=expname, startyear=year, endyear=year, varname=varname, diagname=diagname, format=format)
        try:
            ds.close()
        except:
            pass
        del ds

    logging.info(f"Merging averaged single-year files ...") 
    data = merge_annual_files(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format)

    if cleanup:
        logging.info(f"Clean up averaged single-year files ...") 
        for year in range(startyear, endyear + 1):
            filepath = os.path.join(dirs['post'], f"{varname}_{expname}_{year}-{year}_{diagname}_{format}.nc")
            shutil.rm(filepath)

    return data


##########################################################################################
##########################################################################################

