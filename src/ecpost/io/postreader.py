#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
post I/O module

Produce, store and merge light-weight aggregated data (timeseries, profiles,
hovmoller diagrams, horizontal maps, time-averaged fields) from NEMO output.

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

# dictionary of months by seasons
season_months = {"DJF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}

# diagnostics: allowed time modes (first one is the default) and required dimensionality
DIAGNOSTICS = {
    "scalar":     {"modes": ["global"], "dims": ["2D", "3D"]},
    "timeseries": {"modes": ["plain", "yearly", "monthly", "seasonally", "global"], "dims": ["2D", "3D"]},
    "profile":    {"modes": ["global", "monthly", "seasonally"], "dims": ["3D"]},
    "hovmoller":  {"modes": ["plain", "yearly"], "dims": ["3D"]},
    "map":        {"modes": ["global", "monthly", "seasonally"], "dims": ["2D", "3D"]},
    "field":      {"modes": ["global", "monthly", "seasonally"], "dims": ["2D", "3D"]},
}

# dimensions along which single-year files are concatenated (otherwise: weighted mean)
CONCAT_DIMS = ("time", "year")


def check_diagnostic(varname, diagname, mode):
    """ Raise ValueError if (varname, diagname, mode) is not a valid combination """

    if diagname not in DIAGNOSTICS:
        raise ValueError(f"Unknown diagnostic '{diagname}'. Choose among {list(DIAGNOSTICS)}")
    if mode not in DIAGNOSTICS[diagname]["modes"]:
        raise ValueError(f"Invalid mode '{mode}' for '{diagname}'. Choose among {DIAGNOSTICS[diagname]['modes']}")
    ndim = catalogue.observables('nemo')[varname]['dim']
    if ndim not in DIAGNOSTICS[diagname]["dims"]:
        raise ValueError(f"Diagnostic '{diagname}' requires a {DIAGNOSTICS[diagname]['dims']} variable, '{varname}' is {ndim}")


##########################################################################################
# I/O for averaged data

def get_output_path(postdir, expname, startyear, endyear, varname, diagname, mode, metric='base'):
    """get output file path"""

    suffix = f"_{metric}" if metric != 'base' else ""
    filename = f"{expname}_{startyear}-{endyear}_{varname}_{diagname}_{mode}{suffix}.nc"

    return os.path.join(postdir, filename)


def reader_averaged(expname, startyear, endyear, varname, diagname, mode, metric='base', config_path=None):
    """
    Reader of averaged data

    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [scalar, timeseries, profile, hovmoller, map, field]
        mode: time mode [plain, global, monthly, seasonally, yearly]
        metric: metrics [base, diff, ...]

    """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)

    filename = get_output_path(dirs['post'], expname, startyear, endyear, varname, diagname, mode, metric)
    if not os.path.exists(filename):
        raise FileNotFoundError(filename)
    logging.info('File to be loaded %s', filename)
    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    data = xr.open_dataset(filename, decode_times=time_coder)

    return data


def writer_averaged(data, expname, startyear, endyear, varname, diagname, mode, metric='base', refinfo=None, config_path=None):
    """
    Writer of averaged data

    Args:
        data: data array
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [scalar, timeseries, profile, hovmoller, map, field]
        mode: time mode [plain, global, monthly, seasonally, yearly]
        metric: metrics [base, diff, ...]
        refinfo: reference info
    """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)

    filename = get_output_path(dirs['post'], expname, startyear, endyear, varname, diagname, mode, metric)
    logging.info('File to be written %s', filename)
    data = _finalize(data, varname, diagname, mode, metric)
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


def _finalize(data, varname, diagname, mode, metric='base'):
    """ Make sure data is a Dataset with metadata, ready to be written """

    if isinstance(data, xr.DataArray):
        data = data.to_dataset(name=varname)

    info = catalogue.observables('nemo').get(varname, {})
    if varname in data:
        for key in ('units', 'long_name'):
            if key in info:
                data[varname].attrs.setdefault(key, info[key])

    data.attrs['diagnostic'] = diagname
    data.attrs['mode'] = mode
    data.attrs['metric'] = metric
    data.attrs.setdefault('description', f"{varname} {diagname} ({mode}, {metric})")

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

def _scan_merged(postdir, expname, varname, diagname, mode, metric='base'):
    """ List of multi-year (merged) files in the post folder as dict(file, start, end, span) """

    suffix = f"_{metric}" if metric != 'base' else ""
    pattern = re.compile(rf"{re.escape(expname)}_(\d+)-(\d+)_{re.escape(varname)}_{diagname}_{mode}{suffix}\.nc$")

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


def find_existing_merged(expname, varname, diagname, mode, metric='base', config_path=None):
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

    merged = _scan_merged(dirs['post'], expname, varname, diagname, mode, metric)

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


def _plan_years(postdir, expname, startyear, endyear, varname, diagname, mode, metric='base', replace=False):
    """
    Decide how to build the window [startyear, endyear] for a diagnostic.

    Returns:
        blocks: list of reusable merged blocks
        todo: years whose single-year file has to be computed
    """

    blocks = [] if replace else select_usable_blocks(
        _scan_merged(postdir, expname, varname, diagname, mode, metric), startyear, endyear)

    covered = set()
    for b in blocks:
        covered.update(range(b["start"], b["end"] + 1))

    todo = []
    for year in range(startyear, endyear + 1):
        if year in covered:
            continue
        f = get_output_path(postdir, expname, year, year, varname, diagname, mode, metric)
        if replace or not os.path.exists(f):
            todo.append(year)

    return blocks, todo


def merge_annual_files(expname, startyear, endyear, varname, diagname, mode, metric='base', replace=False, config_path=None):
    """
    Merge single-year files and usable merged blocks into a single dataset covering
    [startyear, endyear], and write it to the post folder.
      - data with a 'time' or 'year' dimension are concatenated in chronological order
      - all other data (climatologies) are averaged, weighting each file by its number of years
    """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)
    postdir = dirs['post']
    fout = get_output_path(postdir, expname, startyear, endyear, varname, diagname, mode, metric)

    # single year: nothing to merge
    if startyear == endyear:
        return reader_averaged(expname, startyear, endyear, varname, diagname, mode, metric, config_path=config_path)

    # list of (file, start, end) to merge
    blocks, _ = _plan_years(postdir, expname, startyear, endyear, varname, diagname, mode, metric, replace=replace)
    pieces = [(b["file"], b["start"], b["end"]) for b in blocks]
    covered = {y for _, y1, y2 in pieces for y in range(y1, y2 + 1)}
    for year in range(startyear, endyear + 1):
        if year in covered:
            continue
        fpath = get_output_path(postdir, expname, year, year, varname, diagname, mode, metric)
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Missing single-year file: {fpath}")
        pieces.append((fpath, year, year))
    pieces.sort(key=lambda p: p[1])

    logging.info(f"Merging {len(pieces)} files ({len(blocks)} merged blocks) into {fout}")

    time_coder = xr.coders.CFDatetimeCoder(use_cftime=True)
    with xr.set_options(keep_attrs=True):

        # concatenation (timeseries, hovmoller, ...)
        with xr.open_dataset(pieces[0][0], decode_times=time_coder) as ds0:
            concat_dim = next((d for d in CONCAT_DIMS if d in ds0.dims), None)

        if concat_dim is not None:
            datasets = []
            for f, _, _ in pieces:
                with xr.open_dataset(f, decode_times=time_coder) as ds:
                    datasets.append(ds.load())
            ds_out = xr.concat(datasets, dim=concat_dim, combine_attrs="drop_conflicts")
            ds_out = ds_out.sortby(concat_dim)

        # incremental weighted mean (profile, map, field, ...)
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


def clean_merged_files(expname, varname, diagname, mode, metric='base', dry_run=True, config_path=None):
    """
    Clean up redundant merged files:
      - keeps the longest merged
      - identifies fully contained merged files for deletion
      - optionally deletes them if dry_run=False
    """

    longest, contained, partial, disjoint = find_existing_merged(expname, varname, diagname, mode, metric, config_path=config_path)

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


def clean_annual_files(expname, startyear, endyear, varname, diagname, mode, metric='base', dry_run=True, config_path=None):
    """
    Delete single-year files for a given variable and experiment.

    Args:
        expname (str): Experiment name.
        startyear (int): Start year of the interval.
        endyear (int): End year of the interval.
        varname (str): Variable name.
        diagname (str): Diagnostics name.
        mode (str): Time mode.
        dry_run (bool): If True, only log files without deleting.
    """

    if startyear == endyear:
        return  # the single-year file is the requested output

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders(expname)

    logging.info(f"{'Dry run: would delete' if dry_run else 'Deleting'} single-year files for {varname} {startyear}-{endyear}:")

    for year in range(startyear, endyear + 1):
        filepath = get_output_path(dirs['post'], expname, year, year, varname, diagname, mode, metric)
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
def averaging(data, varname, diagname, mode, orca, config_path=None):
    """
    Averaging: Perform different flavours of averaging

    Args:
        data: data array of a single field
        varname: variable name
        diagname: diagnostics name [scalar, timeseries, profile, hovmoller, map, field]
        mode: time mode [plain, global, monthly, seasonally, yearly]
        orca: ORCA configuration <ORCA2, eORCA1>

    Output (dimensions besides the time ones set by mode):
        scalar:     none (time and volume/surface mean)
        timeseries: none (volume/surface mean)
        profile:    z (horizontal mean)
        hovmoller:  z (horizontal mean)
        map:        y, x (vertical mean for 3D variables)
        field:      [z], y, x
    """

    check_diagnostic(varname, diagname, mode)
    info = catalogue.observables('nemo')[varname]

    # scalar / single-valued
    if diagname == 'scalar' or (diagname == 'timeseries' and mode == 'global'):
        data = timemean(data=data, mode='global')
        data = spacemean(data=data, ndim=info['dim'], orca=orca, config_path=config_path)

    # timeseries
    elif diagname == 'timeseries':
        data = timemean(data=data, mode=mode)
        data = spacemean(data=data, ndim=info['dim'], orca=orca, config_path=config_path)

    # vertical profile / hovmoller diagram
    elif diagname in ('profile', 'hovmoller'):
        data = timemean(data=data, mode=mode)
        data = spacemean(data=data, ndim='2D', orca=orca, config_path=config_path)

    # 2D horizontal map
    elif diagname == 'map':
        data = timemean(data=data, mode=mode)
        if info['dim'] == '3D':
            data = spacemean(data=data, ndim='1D', orca=orca, config_path=config_path)

    # time-averaged spatial-only field
    elif diagname == 'field':
        data = timemean(data=data, mode=mode)

    return data


######################################################################################################
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
                           diagname='field', mode='global', metric='base', orca=orca,
                           replace=replace, cleanup=cleanup, config_path=config_path)


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
        diagnostics: list of (diagname, mode) tuples
        metric: ['base', 'diff', ...]
        refinfo: dict with keys expname, startyear, endyear of the reference climatology
        orca: ORCA configuration [ORCA2, eORCA1]
        replace: replace existing averaged files [False or True]
        cleanup: clean single-year files and redundant merged files

    Returns:
        dict {(diagname, mode): Dataset}
    """

    diagnostics = list(dict.fromkeys(diagnostics))  # drop duplicates, keep order
    for diagname, mode in diagnostics:
        check_diagnostic(varname, diagname, mode)

    # configure folders
    cfg = Config(config_path=config_path)
    postdir = cfg.folders(expname)['post']

    results = {}
    todo = {}  # (diagname, mode) -> years to be computed
    for diagname, mode in diagnostics:
        f = get_output_path(postdir, expname, startyear, endyear, varname, diagname, mode, metric)
        if os.path.exists(f) and not replace:
            logging.info(f"Averaged data found: {f}")
            results[(diagname, mode)] = reader_averaged(expname, startyear, endyear, varname, diagname, mode, metric, config_path=config_path)
        else:
            _, todo[(diagname, mode)] = _plan_years(postdir, expname, startyear, endyear, varname, diagname, mode, metric, replace=replace)

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
        for (diagname, mode), ylist in todo.items():
            if year not in ylist:
                continue
            data = averaging(data=ds, varname=varname, diagname=diagname, mode=mode, orca=orca, config_path=config_path)
            writer_averaged(data=data, expname=expname, startyear=year, endyear=year, varname=varname, diagname=diagname,
                            mode=mode, metric=metric, refinfo=refinfo, config_path=config_path)
        ds.close()
        del ds

    # Merge
    for diagname, mode in todo:
        logging.info(f"Merging {varname} {diagname} ({mode}) {startyear}-{endyear} ...")
        results[(diagname, mode)] = merge_annual_files(expname=expname, startyear=startyear, endyear=endyear, varname=varname,
                                                       diagname=diagname, mode=mode, metric=metric, replace=replace,
                                                       config_path=config_path)

    if cleanup:
        logging.info(f"Cleaning ...")
        for diagname, mode in diagnostics:
            clean_merged_files(expname=expname, varname=varname, diagname=diagname, mode=mode, metric=metric,
                               dry_run=False, config_path=config_path)
            clean_annual_files(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname,
                               mode=mode, metric=metric, dry_run=False, config_path=config_path)

    return {d: results[d] for d in diagnostics}


def postreader_nemo(expname, startyear, endyear, varname, diagname, mode='global', metric='base', refinfo=None, orca='ORCA2', replace=False, cleanup=False, config_path=None):
    """
    Postreader_nemo: main function for reading averaged data

    Args:
        expname: experiment name
        startyear,endyear: time window
        varname: variable name
        diagname: diagnostics name [scalar, timeseries, profile, hovmoller, map, field]
        mode: time mode [plain, global, monthly, seasonally, yearly]
        metric: ['base', 'diff']
        refinfo: [rexpname, rstartyear, rendyear]
        orca: ORCA configuration [ORCA2, eORCA1]
        replace: replace existing averaged file [False or True]

    """

    results = postreader_nemo_multi(expname=expname, startyear=startyear, endyear=endyear, varname=varname,
                                    diagnostics=[(diagname, mode)], metric=metric, refinfo=refinfo, orca=orca,
                                    replace=replace, cleanup=cleanup, config_path=config_path)

    return results[(diagname, mode)]


##########################################################################################
##########################################################################################
