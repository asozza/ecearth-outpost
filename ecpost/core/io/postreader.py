#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
post I/O module

Author: Alessandro Sozza (CNR-ISAC)
Date: Nov 2025
"""

import os
import re
import shutil
import logging
import numpy as np
import xarray as xr

from ecpost.core.utils import config
from ecpost.core.utils import catalogue   
from ecpost.core.io.reader import reader_nemo_field
from ecpost.core.means.means import spacemean, timemean

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


def merge_annual_files_old(expname, startyear, endyear, varname, diagname, format):
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
    logging.info(f"Merging {len(filelist)} annual averaged files...")

    # Merging annual files
    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    ds = xr.open_mfdataset(filelist, combine='by_coords', decode_times=time_coder)
    writer_averaged(data=ds, expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format)

    return ds


def merge_annual_files(expname, startyear, endyear, varname, diagname, format):
    """
    Merge annual files into a single dataset, reusing merged files when possible.

    Args:
        expname: experiment name
        startyear, endyear: time window
        varname: variable name
        diagname: diagnostics name
        format: time format
    """

    dirs = config.folders(expname)
    all_files = os.listdir(dirs['post'])

    pattern = rf"{varname}_{expname}_(\d+)-(\d+)_{diagname}_{format}\.nc"
    files_info = []

    for f in all_files:
        m = re.match(pattern, f)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            files_info.append((y1, y2, os.path.join(dirs['post'], f)))

    merged_files = [(y1, y2, f) for y1, y2, f in files_info if y1 != y2]
    annual_files = [(y1, f) for y1, y2, f in files_info if y1 == y2]

    # Search for covered years by merged files
    covered_years = set()
    for y1, y2, _ in merged_files:
        covered_years.update(range(y1, y2+1))

    requested_years = set(range(startyear, endyear+1))
    missing_years = requested_years - covered_years

    # prepare list of files to merge
    files_to_merge = []
    for y1, y2, f in merged_files:
        if set(range(y1, y2+1)) & requested_years:
            files_to_merge.append(f)
    for y, f in annual_files:
        if y in missing_years:
            files_to_merge.append(f)

    if not files_to_merge:
        raise FileNotFoundError("No files found for the requested interval.")

    logging.info(f"Merging {len(files_to_merge)} files covering years {startyear}-{endyear}")
    logging.info(f"Missing years merged from annual files: {sorted(missing_years)}")

    # Open dataset, concatenate and write merged file
    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    ds = xr.open_mfdataset(files_to_merge, combine='by_coords', decode_times=time_coder)
    writer_averaged(data=ds, expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format)

    logging.info(f"Merged file for {startyear}-{endyear} written successfully.")

    return ds


def clean_merged_files(expname, varname, diagname, format, dry_run=True):
    """
    Pulizia intelligente dei file merged: identifica il file più lungo,
    classifica tutti gli altri file come:
      - contenuti completamente (ridondanti) -> cancellabili
      - parzialmente sovrapposti
      - disgiunti
    Se dry_run=False cancella automaticamente i file completamente contenuti.
    """

    dirs = config.folders(expname)
    all_files = os.listdir(dirs['post'])

    pattern = rf"{varname}_{expname}_(\d+)-(\d+)_{diagname}_{format}\.nc"

    merged = []

    # Find already merged files
    for fname in all_files:
        m = re.match(pattern, fname)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            if y1 != y2:
                full_path = os.path.join(dirs['post'], fname)
                span = y2 - y1 + 1
                merged.append((y1, y2, span, fname, full_path))

    if not merged:
        logging.info("No merged files found.")
        return None

    # Order by length, then by starting year
    merged.sort(key=lambda x: (-x[2], x[0]))
    longest = merged[0]
    long_y1, long_y2, long_span, long_name, long_path = longest

    logging.info(f"Longest merged file: {long_name} {long_y1}-{long_y2}, {long_span} years)")

    contained = []
    partial = []
    disjoint = []

    for y1, y2, span, fname, fpath in merged[1:]:

        if y1 >= long_y1 and y2 <= long_y2:
            # fully covered 
            contained.append((fname, y1, y2))

        elif y2 < long_y1 or y1 > long_y2:
            # no overlap
            disjoint.append((fname, y1, y2))

        else:
            # partial overlap
            partial.append((fname, y1, y2))

    logging.info(f"Fully contained merged files (safe to delete): {contained}")
    logging.info(f"Partially overlapping merged files: {partial}")
    logging.info(f"Disjoint merged files: {disjoint}")

    # Clean, if asked
    if not dry_run:
        for fname, y1, y2 in contained:
            path = os.path.join(dirs['post'], fname)
            try:
                os.remove(path)
                logging.info(f"Deleted redundant merged file: {fname}")
            except Exception as e:
                logging.error(f"Failed to delete {fname}: {e}")
        logging.info("Cleanup completed.")

    return {"longest": longest,"contained": contained,"partial": partial,"disjoint": disjoint}


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

    # otherwise read original data and perform averaging
    for year in range(startyear, endyear + 1):

        # averaging only on missing single-year averaged files
        f = os.path.join(dirs['post'],f"{varname}_{expname}_{year}-{year}_{diagname}_{format}.nc")
        if os.path.exists(f) and not replace:
            # skipping years
            logging.info(f"Skipping year: {year}") 
        else:
            # processing years
            logging.info(f"Processing year: {year}")    
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

