#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
post I/O module

Produce, store and merge light-weight aggregated data from NEMO output.

Four diagnostics are computed from the raw output (see DIAGNOSTICS):
    timeseries  surface/volume mean, monthly
    hovmoller   horizontal mean, monthly
    map         vertical mean, averaged over the time window
    field       averaged over the time window
Other products (yearly series, seasonal cycles, profiles, scalars) are time averages
of timeseries/hovmoller and are obtained on the fly by get_timeseries/get_profile.

Each diagnostic is computed year by year and stored as a single-year file in the
'post' folder; single-year files are then merged into a file covering the requested
time window. Already merged files are reused when they lie inside the requested window.

Author: Alessandro Sozza (CNR-ISAC)
Date: Nov 2025
"""

import os
import re
import logging
import numpy as np
import xarray as xr

from ecpost.utils import catalogue
from ecpost.utils.config import Config
from ecpost.io.reader import reader_nemo_field
from ecpost.means.means import apply_cost_function, spacemean, timemean

# diagnostics computed from raw data:
#   space: spatial mean ['full': surface/volume, 'horizontal', 'vertical', None]
#   time:  time mean ['plain': none, 'global': over the window] (see timemean)
#   merge: how single-year files are combined ['concat' along time, 'mean' weighted by years]
#   dims:  variables allowed
DIAGNOSTICS = {
    "timeseries": {"space": "full",       "time": "plain",  "merge": "concat", "dims": ["2D", "3D"],
                   "description": "surface/volume mean, monthly"},
    "hovmoller":  {"space": "horizontal", "time": "plain",  "merge": "concat", "dims": ["3D"],
                   "description": "horizontal mean, monthly (time x depth)"},
    "map":        {"space": "vertical",   "time": "global", "merge": "mean",   "dims": ["2D", "3D"],
                   "description": "vertical mean (3D variables), averaged over the window"},
    "field":      {"space": None,         "time": "global", "merge": "mean",   "dims": ["2D", "3D"],
                   "description": "full field, averaged over the window"},
}


def check_diagnostic(varname, diagname):
    """ Raise ValueError if diagnostic is unknown or not applicable to the variable """

    if diagname not in DIAGNOSTICS:
        raise ValueError(f"Unknown diagnostic '{diagname}'. Choose among {list(DIAGNOSTICS)}")
    ndim = catalogue.observables('nemo')[varname]['dim']
    if ndim not in DIAGNOSTICS[diagname]["dims"]:
        raise ValueError(f"Diagnostic '{diagname}' requires a {DIAGNOSTICS[diagname]['dims']} variable, '{varname}' is {ndim}")


##########################################################################################
# I/O for averaged data

def get_output_path(postdir, expname, startyear, endyear, varname, diagname, metric='base'):
    """get output file path"""

    suffix = f"_{metric}" if metric != 'base' else ""
    filename = f"{expname}_{startyear}-{endyear}_{varname}_{diagname}{suffix}.nc"

    return os.path.join(postdir, filename)


def reader_averaged(expname, startyear, endyear, varname, diagname, metric='base', config_path=None):
    """
    Reader of averaged data

    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [timeseries, hovmoller, map, field]
        metric: metrics [base, diff, ...]

    """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)

    filename = get_output_path(dirs['post'], expname, startyear, endyear, varname, diagname, metric)
    if not os.path.exists(filename):
        raise FileNotFoundError(filename)
    logging.info('File to be loaded %s', filename)
    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    data = xr.open_dataset(filename, decode_times=time_coder)

    return data


def writer_averaged(data, expname, startyear, endyear, varname, diagname, metric='base', refinfo=None, config_path=None):
    """
    Writer of averaged data

    Args:
        data: data array
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [timeseries, hovmoller, map, field]
        metric: metrics [base, diff, ...]
        refinfo: reference info
    """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)

    filename = get_output_path(dirs['post'], expname, startyear, endyear, varname, diagname, metric)
    logging.info('File to be written %s', filename)
    data = _finalize(data, varname, diagname, metric)
    if metric != 'base' and refinfo is not None:
        data = update_description(data, refinfo)
    _safe_to_netcdf(data, filename)

    return None


def update_description(data, refinfo):

    description = data.attrs.get('description', 'No description')
    if isinstance(refinfo, dict):
        refinfo_str = ', '.join([f"{key}: {value}" for key, value in refinfo.items()])
        description += f" {refinfo_str}"
    data.attrs['description'] = description

    return data


def _finalize(data, varname, diagname, metric='base'):
    """ Make sure data is a Dataset with metadata, ready to be written """

    if isinstance(data, xr.DataArray):
        data = data.to_dataset(name=varname)

    info = catalogue.observables('nemo').get(varname, {})
    if varname in data:
        for key in ('units', 'long_name'):
            if key in info:
                data[varname].attrs.setdefault(key, info[key])

    data.attrs['diagnostic'] = diagname
    data.attrs['metric'] = metric
    data.attrs.setdefault('description', f"{varname} {diagname}: {DIAGNOSTICS[diagname]['description']} ({metric})")

    return data


def _safe_to_netcdf(data, filename):
    """
    Write to a temporary file and then move it, so that an input file can be safely
    overwritten. Original encodings (chunksizes, ...) are dropped since they may be
    inconsistent with the reduced dimensions.
    """

    tmpfile = filename + '.tmp'
    data = data.drop_encoding()
    data.to_netcdf(tmpfile, mode='w', engine='netcdf4', format='NETCDF4')
    os.replace(tmpfile, filename)


##########################################################################################
# merging functions

def _scan_merged(postdir, expname, varname, diagname, metric='base'):
    """ List of multi-year (merged) files in the post folder as dict(file, start, end, span) """

    suffix = f"_{metric}" if metric != 'base' else ""
    pattern = re.compile(rf"{re.escape(expname)}_(\d+)-(\d+)_{re.escape(varname)}_{diagname}{suffix}\.nc$")

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

    return merged


def find_existing_merged(expname, varname, diagname, metric='base', config_path=None):
    """
    Scan the post directory for merged files of a given variable,
    classify them into:
      - longest : the merged file with the largest time span
      - contained : fully contained in another merged file
      - partial : partially overlapping with the longest
      - disjoint : no overlap with the longest
    """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)

    merged = _scan_merged(dirs['post'], expname, varname, diagname, metric)

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

    logging.debug({
        "longest": longest,
        "contained": contained,
        "partial": partial,
        "disjoint": disjoint
    })

    return longest, contained, partial, disjoint


def select_usable_blocks(blocks, startyear, endyear):
    """
    Select merged blocks that can be reused for the window [startyear, endyear]:
    only blocks fully inside the window, without overlaps among them (longest first).
    """

    candidates = [b for b in blocks if b["start"] >= startyear and b["end"] <= endyear]
    candidates.sort(key=lambda b: b["span"], reverse=True)

    selected = []
    for b in candidates:
        if all(b["end"] < s["start"] or b["start"] > s["end"] for s in selected):
            selected.append(b)

    selected.sort(key=lambda x: x["start"])

    for b in selected:
        logging.info(f"Usable merged block: {b['file']} [{b['start']}-{b['end']}]")

    return selected


def _plan_years(postdir, expname, startyear, endyear, varname, diagname, metric='base', replace=False):
    """
    Decide how to build the window [startyear, endyear] for a diagnostic.

    Returns:
        blocks: list of reusable merged blocks
        todo: years whose single-year file has to be computed
    """

    blocks = [] if replace else select_usable_blocks(
        _scan_merged(postdir, expname, varname, diagname, metric), startyear, endyear)

    covered = set()
    for b in blocks:
        covered.update(range(b["start"], b["end"] + 1))

    todo = []
    for year in range(startyear, endyear + 1):
        if year in covered:
            continue
        f = get_output_path(postdir, expname, year, year, varname, diagname, metric)
        if replace or not os.path.exists(f):
            todo.append(year)

    return blocks, todo


def merge_annual_files(expname, startyear, endyear, varname, diagname, metric='base', replace=False, config_path=None):
    """
    Merge single-year files and usable merged blocks into a single dataset covering
    [startyear, endyear], and write it to the post folder.
      - 'concat' diagnostics are concatenated along time in chronological order
      - 'mean' diagnostics are averaged, weighting each file by its number of years
    """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)
    postdir = dirs['post']
    fout = get_output_path(postdir, expname, startyear, endyear, varname, diagname, metric)

    # single year: nothing to merge
    if startyear == endyear:
        return reader_averaged(expname, startyear, endyear, varname, diagname, metric, config_path=config_path)

    # list of (file, start, end) to merge
    blocks, _ = _plan_years(postdir, expname, startyear, endyear, varname, diagname, metric, replace=replace)
    pieces = [(b["file"], b["start"], b["end"]) for b in blocks]
    covered = {y for _, y1, y2 in pieces for y in range(y1, y2 + 1)}
    for year in range(startyear, endyear + 1):
        if year in covered:
            continue
        fpath = get_output_path(postdir, expname, year, year, varname, diagname, metric)
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Missing single-year file: {fpath}")
        pieces.append((fpath, year, year))
    pieces.sort(key=lambda p: p[1])

    logging.info(f"Merging {len(pieces)} files ({len(blocks)} merged blocks) into {fout}")

    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    with xr.set_options(keep_attrs=True):

        # concatenation (timeseries, hovmoller)
        if DIAGNOSTICS[diagname]["merge"] == "concat":
            datasets = []
            for f, _, _ in pieces:
                with xr.open_dataset(f, decode_times=time_coder) as ds:
                    datasets.append(ds.load())
            ds_out = xr.concat(datasets, dim="time", combine_attrs="drop_conflicts")
            ds_out = ds_out.sortby("time")

        # incremental weighted mean (map, field)
        else:
            total_sum = None
            total_weight = 0
            for f, y1, y2 in pieces:
                w = y2 - y1 + 1
                with xr.open_dataset(f, decode_times=time_coder) as ds:
                    contrib = ds.load() * w
                total_sum = contrib if total_sum is None else total_sum + contrib
                total_weight += w
            ds_out = total_sum / total_weight
            ds_out.attrs["n_years"] = np.int32(total_weight)

    ds_out.attrs["merged_range"] = f"{startyear}-{endyear}"

    logging.info(f"Writing merged dataset to: {fout}")
    _safe_to_netcdf(ds_out, fout)

    return ds_out


def clean_merged_files(expname, varname, diagname, metric='base', dry_run=True, config_path=None):
    """
    Clean up redundant merged files:
      - keeps the longest merged
      - identifies fully contained merged files for deletion
      - optionally deletes them if dry_run=False
    """

    longest, contained, partial, disjoint = find_existing_merged(expname, varname, diagname, metric, config_path=config_path)

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

    logging.debug(f"Merged file cleanup summary:\n{summary}")
    return summary


def clean_annual_files(expname, startyear, endyear, varname, diagname, metric='base', dry_run=True, config_path=None):
    """
    Delete single-year files for a given variable and experiment.

    Args:
        expname (str): Experiment name.
        startyear (int): Start year of the interval.
        endyear (int): End year of the interval.
        varname (str): Variable name.
        diagname (str): Diagnostics name.
        dry_run (bool): If True, only log files without deleting.
    """

    if startyear == endyear:
        return  # the single-year file is the requested output

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)

    logging.info(f"{'Dry run: would delete' if dry_run else 'Deleting'} single-year files for {varname} {startyear}-{endyear}:")

    for year in range(startyear, endyear + 1):
        filepath = get_output_path(dirs['post'], expname, year, year, varname, diagname, metric)
        if os.path.exists(filepath):
            if dry_run:
                logging.info(f"  - {filepath}")
            else:
                try:
                    os.remove(filepath)
                    logging.info(f"Deleted: {filepath}")
                except Exception as e:
                    logging.error(f"Failed to delete {filepath}: {e}")

    logging.info("Single-year file cleanup completed.")


##########################################################################################
# averaging functions
def averaging(data, varname, diagname, orca, config_path=None):
    """
    Averaging: apply the time and space means of a diagnostic (see DIAGNOSTICS)

    Args:
        data: data array of a single field
        varname: variable name
        diagname: diagnostics name [timeseries, hovmoller, map, field]
        orca: ORCA configuration <ORCA2, eORCA1>

    """

    check_diagnostic(varname, diagname)
    ndim = catalogue.observables('nemo')[varname]['dim']
    diag = DIAGNOSTICS[diagname]

    data = timemean(data=data, mode=diag["time"])

    if diag["space"] == "full":
        data = spacemean(data=data, ndim=ndim, orca=orca, config_path=config_path)
    elif diag["space"] == "horizontal":
        data = spacemean(data=data, ndim='2D', orca=orca, config_path=config_path)
    elif diag["space"] == "vertical" and ndim == '3D':
        data = spacemean(data=data, ndim='1D', orca=orca, config_path=config_path)

    return data


##############################################################################################################################################################
##############################################################################################################################################################
# MAIN FUNCTIONS
def postreader_nemo_multi(expname, startyear, endyear, varname, diagnostics, metric='base', refinfo=None, orca='ORCA2',
                          replace=False, cleanup=False, config_path=None):
    """
    Compute (or read, if available) several diagnostics of a variable, reading the raw
    NEMO output only once per year.

    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagnostics: list of diagnostics names [timeseries, hovmoller, map, field]
        metric: ['base', 'diff', ...]
        refinfo: dict with keys expname, startyear, endyear of the reference climatology
        orca: ORCA configuration [ORCA2, eORCA1]
        replace: replace existing averaged files [False or True]
        cleanup: clean single-year files and redundant merged files

    Returns:
        dict {diagname: Dataset}
    """

    diagnostics = list(dict.fromkeys(diagnostics))  # drop duplicates, keep order
    for diagname in diagnostics:
        check_diagnostic(varname, diagname)

    # configure folders
    cfg = Config(config_path=config_path)
    postdir = cfg.folders(expname)['post']

    results = {}
    todo = {}  # diagname -> years to be computed
    for diagname in diagnostics:
        f = get_output_path(postdir, expname, startyear, endyear, varname, diagname, metric)
        if os.path.exists(f) and not replace:
            logging.info(f"Averaged data found: {f}")
            results[diagname] = reader_averaged(expname, startyear, endyear, varname, diagname, metric, config_path=config_path)
        else:
            _, todo[diagname] = _plan_years(postdir, expname, startyear, endyear, varname, diagname, metric, replace=replace)

    years = sorted({y for ylist in todo.values() for y in ylist})

    ds_ref = None
    if years and metric != 'base':
        if refinfo is None:
            raise ValueError(f"metric='{metric}' requires refinfo")
        ds_ref = get_climatology(expname=refinfo['expname'], startyear=refinfo['startyear'], endyear=refinfo['endyear'],
                                 varname=varname, orca=orca, config_path=config_path)

    # Loop over missing years: read raw data once, compute all diagnostics needing it
    for year in years:
        logging.info(f"Processing {varname} year {year}: {[d for d, ylist in todo.items() if year in ylist]}")
        ds = reader_nemo_field(expname=expname, startyear=year, endyear=year, varname=varname, config_path=config_path)
        if ds_ref is not None:
            ds = apply_cost_function(data=ds, data_ref=ds_ref, metric=metric)
        for diagname, ylist in todo.items():
            if year not in ylist:
                continue
            data = averaging(data=ds, varname=varname, diagname=diagname, orca=orca, config_path=config_path)
            writer_averaged(data=data, expname=expname, startyear=year, endyear=year, varname=varname, diagname=diagname,
                            metric=metric, refinfo=refinfo, config_path=config_path)
        ds.close()
        del ds

    # Merge
    for diagname in todo:
        logging.info(f"Merging {varname} {diagname} {startyear}-{endyear} ...")
        results[diagname] = merge_annual_files(expname=expname, startyear=startyear, endyear=endyear, varname=varname,
                                               diagname=diagname, metric=metric, replace=replace, config_path=config_path)

    if cleanup:
        logging.info(f"Cleaning ...")
        for diagname in diagnostics:
            clean_merged_files(expname=expname, varname=varname, diagname=diagname, metric=metric,
                               dry_run=False, config_path=config_path)
            clean_annual_files(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname,
                               metric=metric, dry_run=False, config_path=config_path)

    return {d: results[d] for d in diagnostics}


def postreader_nemo(expname, startyear, endyear, varname, diagname, metric='base', refinfo=None, orca='ORCA2', replace=False, cleanup=False, config_path=None):
    """
    Postreader_nemo: main function for reading averaged data

    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [timeseries, hovmoller, map, field]
        metric: ['base', 'diff']
        refinfo: [rexpname, rstartyear, rendyear]
        orca: ORCA configuration [ORCA2, eORCA1]
        replace: replace existing averaged file [False or True]

    """

    results = postreader_nemo_multi(expname=expname, startyear=startyear, endyear=endyear, varname=varname,
                                    diagnostics=[diagname], metric=metric, refinfo=refinfo, orca=orca,
                                    replace=replace, cleanup=cleanup, config_path=config_path)

    return results[diagname]


##########################################################################################
# derived products: time averages of the stored diagnostics

def get_climatology(expname, startyear, endyear, varname, orca='ORCA2', replace=False, cleanup=False, config_path=None):
    """
    Get climatological reference field (time-averaged field over the window).

    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        orca: ORCA configuration [ORCA2, eORCA1]
        replace: replace existing averaged file [False or True]
        cleanup: clean single-year files and other merged files

    """

    return postreader_nemo(expname=expname, startyear=startyear, endyear=endyear, varname=varname,
                           diagname='field', orca=orca, replace=replace, cleanup=cleanup, config_path=config_path)


def get_timeseries(expname, startyear, endyear, varname, mode='plain', **kwargs):
    """
    Surface/volume mean of a variable, from the 'timeseries' diagnostic.

    Args:
        mode: time mean [plain, yearly, monthly, seasonally, global]
              plain: monthly series, yearly: annual means, monthly/seasonally: seasonal cycle,
              global: single value over the window
        kwargs: passed to postreader_nemo (metric, refinfo, orca, replace, config_path, ...)
    """

    data = postreader_nemo(expname, startyear, endyear, varname, 'timeseries', **kwargs)

    return timemean(data=data, mode=mode)


def get_hovmoller(expname, startyear, endyear, varname, mode='plain', **kwargs):
    """
    Horizontal mean of a 3D variable as function of time and depth, from the 'hovmoller' diagnostic.

    Args:
        mode: time mean [plain, yearly]
        kwargs: passed to postreader_nemo (metric, refinfo, orca, replace, config_path, ...)
    """

    data = postreader_nemo(expname, startyear, endyear, varname, 'hovmoller', **kwargs)

    return timemean(data=data, mode=mode)


def get_profile(expname, startyear, endyear, varname, mode='global', **kwargs):
    """
    Vertical profile (horizontal mean) of a 3D variable, from the 'hovmoller' diagnostic.

    Args:
        mode: time mean [global, monthly, seasonally]
        kwargs: passed to postreader_nemo (metric, refinfo, orca, replace, config_path, ...)
    """

    return get_hovmoller(expname, startyear, endyear, varname, mode=mode, **kwargs)


##########################################################################################
##########################################################################################
