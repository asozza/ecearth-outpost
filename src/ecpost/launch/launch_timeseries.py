#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command line tool to plot the timeseries (surface/volume mean) of NEMO variables for one or
more EC-Earth4 experiments in the same figure. Data are read from the aggregated 'timeseries'
diagnostic (produced on the fly if missing, see climatology). One figure per variable is
written in the 'post' folder of the first experiment (see launch/common.py) as
<expname1>[-<expname2>...]_<startyear>-<endyear>_<varname>_timeseries[_<mode>][_movave][_<metric>].<fmt>

Examples:
    timeseries -e cs00 1990 1999 -v thetao tos
    timeseries -e cs00 1990 1999 -e cs01 1990 2009 -v thetao --mode yearly --labels control warming
    timeseries -e cs01 1990 1999 -v thetao --metric diff --ref cs00 1990 1999 --config config.yml

Authors: Alessandro Sozza (CNR-ISAC)
Date: Oct 2026
"""

import argparse
import logging
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ecpost.utils import catalogue
from ecpost.graphics.timeseries import plot_timeseries
from ecpost.launch.common import add_common_arguments, check_common_arguments, get_postdir, get_figure_path, print_summary

MODES = ["plain", "yearly", "monthly", "seasonally"]


def parse_args(argv=None):
    """Command line parser for timeseries"""

    parser = argparse.ArgumentParser(
        description="Plot timeseries (surface/volume mean) of NEMO variables for one or more experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    add_common_arguments(parser)
    parser.add_argument("--mode", default="plain", choices=MODES,
                        help="Time mean: plain (monthly), yearly, monthly/seasonally (seasonal cycle)")
    parser.add_argument("--moving", action="store_true", help="Apply a 12-month moving average (mode=plain only)")
    parser.add_argument("--rescale", action="store_true", help="Rescale each series by its initial value")
    parser.add_argument("--timeoff", type=float, default=0, help="Offset added to the time axis")

    parsed = parser.parse_args(argv)
    check_common_arguments(parser, parsed)

    if parsed.moving and parsed.mode != "plain":
        parser.error("--moving requires --mode plain")

    return parsed


def main(argv=None):

    # parser
    args = parse_args(argv)
    logging.getLogger().setLevel(logging.INFO)

    # figures go in the post folder of the first experiment
    postdir = get_postdir(args.exps, config_path=args.config_file)

    avetype = "moving" if args.moving else "standard"
    marker = "o" if args.mode in ("monthly", "seasonally") else None

    varlist = catalogue.observables('nemo')
    produced, failed = [], []
    for varname in args.vars:

        if varname not in varlist:
            logging.error(f"Unknown variable '{varname}': skipped")
            failed.append((varname, "unknown variable"))
            continue
        info = varlist[varname]

        fig, ax = plt.subplots(figsize=(10, 5))
        nplotted = 0
        for exp, label in zip(args.exps, args.labels):
            try:
                plot_timeseries(exp["expname"], exp["startyear"], exp["endyear"], varname, mode=args.mode,
                                reader="post", orca=args.orca, replace=args.replace, metric=args.metric,
                                refinfo=args.refinfo, config_path=args.config_file, rescale=args.rescale,
                                avetype=avetype, timeoff=args.timeoff, marker=marker, label=label, ax=ax)
                nplotted += 1
            except Exception as e:
                logging.exception(f"Failed to plot {varname} for {exp['expname']}: {e}")
                failed.append((f"{varname} {exp['expname']}", str(e)))

        if nplotted == 0:
            plt.close(fig)
            continue

        # figure settings
        xlabels = {"plain": "time [years]", "yearly": "time [years]", "monthly": "month", "seasonally": "season"}
        ax.set_xlabel(xlabels[args.mode])
        ylabel = info['long_name'] if args.rescale else f"{info['long_name']} [{info['units']}]"
        if args.metric != "base":
            ylabel = f"{ylabel} ({args.metric} vs {args.refinfo['expname']})"
        ax.set_ylabel(ylabel)
        ax.set_title(f"{varname} timeseries" + (f" ({args.mode})" if args.mode != "plain" else ""))
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()

        suffixes = [args.mode if args.mode != "plain" else None, "movave" if args.moving else None]
        figname = get_figure_path(postdir, args.exps, varname, "timeseries", suffixes=suffixes,
                                  metric=args.metric, fmt=args.fmt)
        fig.savefig(figname, dpi=args.dpi)
        plt.close(fig)
        produced.append(figname)

    return print_summary(produced, failed)


if __name__ == "__main__":
    sys.exit(main())
