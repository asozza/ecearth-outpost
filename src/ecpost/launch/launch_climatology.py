#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command line tool to produce light-weight aggregated data from the NEMO output of an
EC-Earth4 experiment: timeseries, vertical profiles, hovmoller diagrams, horizontal maps
and time-averaged fields. Files are written in the experiment 'post' folder as
<expname>_<startyear>-<endyear>_<varname>_<diagname>[_<metric>].nc

Examples:
    climatology cs00 1990 1999 -v thetao tos
    climatology cs00 1990 1999 -v thetao -d timeseries hovmoller --config config.yml
    climatology cs01 1990 1999 -v thetao -d hovmoller --metric diff --ref cs00 1990 1999

Needed modules:
# module load intel/2021.4.0 intel-mkl/19.0.5 prgenv/intel hdf5 netcdf4
# export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/apps/netcdf4/4.9.1/INTEL/2021.4/lib:/usr/local/apps/hdf5/1.12.2/INTEL/2021.4/lib

Authors: Alessandro Sozza (CNR-ISAC)
Date: May 2024
"""

import argparse
import logging
import sys

from ecpost.utils import catalogue
from ecpost.utils.config import Config
from ecpost.io.postreader import DIAGNOSTICS, check_diagnostic, get_output_path, postreader_nemo_multi


def parse_args(argv=None):
    """Command line parser for climatology"""

    parser = argparse.ArgumentParser(
        description="Produce aggregated data (timeseries, hovmoller, maps, fields) from NEMO output",
        epilog="diagnostics:\n" + "\n".join(f"  {d:<12}{v['description']}" for d, v in DIAGNOSTICS.items()),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # positional arguments (mandatory)
    parser.add_argument("expname", metavar="EXPNAME", help="Experiment name")
    parser.add_argument("startyear", metavar="STARTYEAR", help="Starting year", type=int)
    parser.add_argument("endyear", metavar="ENDYEAR", help="Ending year", type=int)

    # optional arguments
    parser.add_argument("-v", "--vars", nargs="+", required=True, metavar="VAR", help="NEMO variable names (see catalogue)")
    parser.add_argument("-d", "--diags", nargs="+", default=list(DIAGNOSTICS), choices=list(DIAGNOSTICS), metavar="DIAG",
                        help="Diagnostics to produce (default: all, see list below)")
    parser.add_argument("--orca", default="ORCA2", help="ORCA configuration [ORCA2, eORCA1]")
    parser.add_argument("--config", dest="config_file", default=None, help="Configuration file (default: ./config.yml)")
    parser.add_argument("--metric", default="base", help="Metric with respect to the reference climatology [base, diff, ...]")
    parser.add_argument("--ref", nargs=3, metavar=("REFEXP", "REFSTART", "REFEND"), help="Reference experiment and time window (needed by --metric)")
    parser.add_argument("--replace", action="store_true", help="Recompute and replace existing aggregated files")
    parser.add_argument("--cleanup", action="store_true", help="Remove single-year and redundant merged files after merging")
    parser.add_argument("--quiet", action="store_true", help="Do not print the aggregated data")

    parsed = parser.parse_args(argv)

    if parsed.endyear < parsed.startyear:
        parser.error("ENDYEAR must be >= STARTYEAR")
    if parsed.metric != "base" and parsed.ref is None:
        parser.error("--metric requires --ref REFEXP REFSTART REFEND")

    return parsed


def main(argv=None):

    # parser
    args = parse_args(argv)
    logging.getLogger().setLevel(logging.INFO)

    refinfo = None
    if args.ref is not None:
        refinfo = {"expname": args.ref[0], "startyear": int(args.ref[1]), "endyear": int(args.ref[2])}

    # define folders
    config = Config(config_path=args.config_file)
    dirs = config.folders(args.expname)

    varlist = catalogue.observables('nemo')
    produced, failed = [], []
    for varname in args.vars:

        if varname not in varlist:
            logging.error(f"Unknown variable '{varname}': skipped")
            failed.append((varname, "unknown variable"))
            continue

        # keep only the diagnostics compatible with the variable
        valid = []
        for diagname in args.diags:
            try:
                check_diagnostic(varname, diagname)
                valid.append(diagname)
            except ValueError as e:
                logging.warning(f"Skipping {varname} {diagname}: {e}")
        if not valid:
            continue

        try:
            results = postreader_nemo_multi(expname=args.expname, startyear=args.startyear, endyear=args.endyear,
                                            varname=varname, diagnostics=valid, metric=args.metric, refinfo=refinfo,
                                            orca=args.orca, replace=args.replace, cleanup=args.cleanup,
                                            config_path=args.config_file)
        except Exception as e:
            logging.exception(f"Failed to process {varname}: {e}")
            failed.append((varname, str(e)))
            continue

        for diagname, data in results.items():
            filename = get_output_path(dirs['post'], args.expname, args.startyear, args.endyear,
                                       varname, diagname, args.metric)
            produced.append(filename)
            if not args.quiet:
                print(f"\n=== {varname} | {diagname} | {args.metric} ===")
                print(f"file: {filename}")
                print(data.load())
            data.close()

    print("\nSummary:")
    for f in produced:
        print(f"  [ok]   {f}")
    for varname, err in failed:
        print(f"  [fail] {varname}: {err}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
