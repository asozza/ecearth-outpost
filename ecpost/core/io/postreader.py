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

MERGE_RULES = {
    "timeseries": "concat",
    "hovmoller": "concat",
    "profile": "mean",
    "map": "mean",
    "section": "mean"
}

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


##########################################################################################
# merging functions for timeseries

def find_existing_merged(varname, expname, diagname, format):
    """
    Scan the post directory for merged files of a given variable,
    classify them into:
      - longest : the merged file with the largest time span
      - contained : fully contained in another merged file
      - partial : partially overlapping with the longest
      - disjoint : no overlap with the longest
    """
    dirs = config.folders(expname)
    postdir = dirs['post']

    pattern = re.compile(rf"{re.escape(varname)}_{re.escape(expname)}_(\d+)-(\d+)_{diagname}_{format}\.nc")

    merged = []
    for fname in os.listdir(postdir):
        m = pattern.match(fname)
        if not m:
            continue
        start, end = map(int, m.groups())
        if start == end:
            continue  # skip single-year files
        merged.append({
            "file": os.path.join(postdir, fname),
            "start": start,
            "end": end,
            "span": end - start + 1
        })

    if not merged:
        logging.info("No merged files found.")
        return None, [], [], []

    # Find the longest merged file
    longest = max(merged, key=lambda x: x["span"])

    contained = []
    partial = []
    disjoint = []

    LY1, LY2 = longest["start"], longest["end"]

    for m in merged:
        if m is longest:
            continue
        y1, y2 = m["start"], m["end"]
        if y1 >= LY1 and y2 <= LY2:
            contained.append(m)
        elif y2 < LY1 or y1 > LY2:
            disjoint.append(m)
        else:
            partial.append(m)

    logging.info({
        "longest": longest,
        "contained": contained,
        "partial": partial,
        "disjoint": disjoint
    })

    return longest, contained, partial, disjoint

def overlaps(b, y1, y2):
    return not (b["end"] < y1 or b["start"] > y2)

def select_usable_blocks(longest, contained, partial, disjoint, startyear, endyear):
    """
    Return a list of usable merged blocks, keeping:
      - the longest merged
      - disjoint files
    Automatically remove any block completely contained in another.
    """
    if not longest:
        return []

    blocks = [longest] + disjoint

    # tieni solo quelli che intersecano l'intervallo richiesto
    blocks = [b for b in blocks if overlaps(b, startyear, endyear)]

    # Remove blocks fully contained in others
    filtered = []
    for b in blocks:
        keep = True
        for other in blocks:
            if other is b:
                continue
            if b["start"] >= other["start"] and b["end"] <= other["end"]:
                keep = False
                break
        if keep:
            filtered.append(b)

    filtered.sort(key=lambda x: x["start"])

    logging.info("Usable merged blocks:")
    for b in filtered:
        logging.info(f"  - {b['file']} [{b['start']}-{b['end']}]")

    return filtered

def parse_years_from_filename(fname):
    """
    Extract (start, end, weight) from filename
    es: var_exp_2000-2009_profile.nc -> (2000, 2009, 10)
    """
    m = re.search(r"_(\d{4})-(\d{4})_", fname)
    if not m:
        raise ValueError(f"Cannot parse years from filename: {fname}")
    y0 = int(m.group(1))
    y1 = int(m.group(2))

    return y0, y1, y1 - y0 + 1

def merge_annual_files(expname, startyear, endyear, varname, diagname, format):
    """
    Merge single-year files and usable merged blocks into a single dataset.
    Ensures no overlapping time coordinates and chronological order.
    """
    dirs = config.folders(expname)
    postdir = dirs['post']

    # Pattern for single-year files
    single_pattern = f"{varname}_{expname}_{{year}}-{{year}}_{diagname}_{format}.nc"

    # 1) Find existing merged files
    longest, contained, partial, disjoint = find_existing_merged(varname, expname, diagname, format)
    usable_blocks = select_usable_blocks(longest, contained, partial, disjoint, startyear, endyear)

    # 2) Determine which years are covered by merged blocks
    covered_years = set()
    for b in usable_blocks:
        covered_years.update(range(b["start"], b["end"] + 1))

    requested_years = set(range(startyear, endyear + 1))
    missing_years = sorted(requested_years - covered_years)

    logging.info(f"Requested years: {startyear}-{endyear}")
    logging.info(f"Years covered by merged blocks: {sorted(covered_years)}")
    logging.info(f"Missing single years: {missing_years}")

    # 3) Prepare list of files to merge
    files_to_merge = [b["file"] for b in usable_blocks]

    for y in missing_years:
        fpath = os.path.join(postdir, single_pattern.format(year=y))
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Missing single-year file: {fpath}")
        files_to_merge.append(fpath)

    if not files_to_merge:
        raise RuntimeError("No files found to merge!")

    files_to_merge.sort()
    logging.info("Final list of files to merge:")
    for f in files_to_merge:
        logging.info(f"  - {f}")

    # --------------------------------------------------
    # OPENING FILES
    # --------------------------------------------------
    datasets = []
    weights = []

    for f in files_to_merge:
        ds = xr.open_dataset(f)
        _, _, w = parse_years_from_filename(os.path.basename(f))
        datasets.append(ds)
        weights.append(w)

    # --------------------------------------------------
    # MERGE LOGIC
    # --------------------------------------------------
    if diagname in ("timeseries", "hovmoller"):

        ds_out = xr.concat(datasets, dim="time", combine_attrs="drop_conflicts")
        ds_out = ds_out.sortby("time")
        ds_out = ds_out.convert_calendar("gregorian", use_cftime=True)

    elif diagname in ("profile", "map", "section"):

        # incremental weighted mean
        total_sum = None
        total_weight = 0

        for ds, w in zip(datasets, weights):
            contrib = ds * w
            if total_sum is None:
                total_sum = contrib
            else:
                total_sum = total_sum + contrib
            total_weight += w

        ds_out = total_sum / total_weight

        if "time" in ds_out:
            ds_out = ds_out.drop_vars("time", errors="ignore")

        # useful metadata
        ds_out.attrs["n_years"] = np.int32(total_weight)
        ds_out.attrs["merged_range"] = f"{startyear}-{endyear}"

    else:
        raise NotImplementedError(f"Unknown diagname: {diagname}")

    # --------------------------------------------------
    # WRITE MERGED OUTPUT
    # --------------------------------------------------
    fout = os.path.join(postdir, f"{varname}_{expname}_{startyear}-{endyear}_{diagname}_{format}.nc")
    logging.info(f"Writing merged dataset to: {fout}")
    ds_out.to_netcdf(fout)
    logging.info("Merge complete.")

    return ds_out


def clean_merged_files(expname, varname, diagname, format, dry_run=True):
    """
    Clean up redundant merged files:
      - keeps the longest merged
      - identifies fully contained merged files for deletion
      - optionally deletes them if dry_run=False
    """
    dirs = config.folders(expname)
    postdir = dirs['post']

    longest, contained, partial, disjoint = find_existing_merged(varname, expname, diagname, format)

    if not longest:
        logging.info("No merged files found to clean.")
        return

    logging.info(f"Longest merged file: {longest['file']} [{longest['start']}-{longest['end']}]")
    logging.info(f"Fully contained files (candidate for deletion): {[c['file'] for c in contained]}")
    logging.info(f"Partially overlapping files: {[p['file'] for p in partial]}")
    logging.info(f"Disjoint files: {[d['file'] for d in disjoint]}")

    if contained and not dry_run:
        for c in contained:
            try:
                os.remove(c['file'])
                logging.info(f"Deleted redundant merged file: {c['file']}")
            except Exception as e:
                logging.error(f"Failed to delete {c['file']}: {e}")

    if dry_run:
        logging.info("Dry run enabled. No files were deleted.")

    summary = {
        "longest": longest,
        "contained": contained,
        "partial": partial,
        "disjoint": disjoint
    }

    logging.info(f"Merged file cleanup summary:\n{summary}")
    return summary


def clean_annual_files(expname, startyear, endyear, varname, diagname, format, dry_run=True):
    """
    Delete single-year files for a given variable and experiment.

    Args:
        expname (str): Experiment name.
        startyear (int): Start year of the interval.
        endyear (int): End year of the interval.
        varname (str): Variable name.
        diagname (str): Diagnostics name.
        format (str): Time format.
        dry_run (bool): If True, only log files without deleting.
    """
    dirs = config.folders(expname)
    postdir = dirs['post']

    logging.info(f"{'Dry run: would delete' if dry_run else 'Deleting'} single-year files for {varname} {startyear}-{endyear}:")

    for year in range(startyear, endyear + 1):
        filepath = os.path.join(postdir, f"{varname}_{expname}_{year}-{year}_{diagname}_{format}.nc")
        if os.path.exists(filepath):
            if dry_run:
                logging.info(f"  - {filepath}")
            else:
                try:
                    os.remove(filepath)
                    logging.info(f"Deleted: {filepath}")
                except Exception as e:
                    logging.error(f"Failed to delete {filepath}: {e}")
        else:
            logging.warning(f"File not found, skipping: {filepath}")

    logging.info("Single-year file cleanup completed.")


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
    averaged_exists = False
    try:
        if not replace:
            data = reader_averaged(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format)
            logging.info('Averaged data found.')
            averaged_exists = True
        else:
            # When replace is True, skip checking for the file and recreate it
            raise FileNotFoundError  # Trigger the exception deliberately to skip reading of averaged file
    except FileNotFoundError:
        if replace:
            logging.info('Averaged data to be replaced. Creating new file ...')
        else:
            logging.info('Averaged data not found. Creating new file ...')

    if not averaged_exists:

        # try find already merged files (sommething's wrong here!)
        longest, contained, partial, disjoint = find_existing_merged(varname, expname, diagname, format)
        usable_blocks = select_usable_blocks(longest, contained, partial, disjoint, startyear, endyear)    
    
        # determine which years are already covered by merged files
        covered_years = set()
        for b in usable_blocks:
            # keep only years in the requested interval
            for y in range(max(startyear, b["start"]), min(endyear, b["end"]) + 1):
                covered_years.add(y)        

        # Loop over requested years and create only missing ones
        for year in range(startyear, endyear + 1):

            if year in covered_years:
                logging.info(f"Skipping year (already covered by merged file): {year}")
                continue

            # averaging only on missing single-year averaged files
            f = os.path.join(dirs['post'],f"{varname}_{expname}_{year}-{year}_{diagname}_{format}.nc")
            if os.path.exists(f) and not replace:
                # skipping single years
                logging.info(f"Skipping year: {year}") 
            else:
                # processing single years
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
        logging.info(f"Cleaning ...")
        dry_run=False
        clean_merged_files(expname=expname, varname=varname, diagname=diagname, format=format, dry_run=dry_run)
        clean_annual_files(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format, dry_run=dry_run)

    return data


##########################################################################################
##########################################################################################

