#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command line tool to plot the timeseries of 3D NEMO variables averaged over depth layers,
one panel per layer (default 0-100, 100-300, 300-700, 700-2000, 2000-bottom m and the full
column), for one or more EC-Earth4 experiments in the same figure. Data are read from the
aggregated 'hovmoller' diagnostic (produced on the fly if missing, see climatology) and each
level is weighted by its wet volume. One figure per variable is written in the 'post' folder
of the first experiment (see launch/common.py) as
<expname1>[-<expname2>...]_<startyear>-<endyear>_<varname>_layers[_<mode>][_movave][_<metric>].<fmt>

Examples:
    layers -e cs00 1990 1999 -v thetao so
    layers -e cs00 1990 1999 -e cs01 1990 2009 -v thetao --mode yearly --labels control warming
    layers -e cs00 1990 1999 -v thetao --layers 0 700 2000
    layers -e cs01 1990 1999 -v thetao --metric diff --ref cs00 1990 1999 --config config.yml

Authors: Alessandro Sozza (CNR-ISAC)
Date: Oct 2026
"""

import argparse
import logging
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from ecpost.utils import catalogue
from ecpost.io.postreader import check_diagnostic
from ecpost.graphics.timeseries import LAYERS, plot_timeseries_by_layers
from ecpost.launch.common import add_common_arguments, check_common_arguments, get_postdir, get_figure_path, print_summary

MODES = ["plain", "yearly", "monthly", "seasonally"]


def parse_args(argv=None):
    """Command line parser for layers"""

    parser = argparse.ArgumentParser(
        description="Plot timeseries of 3D NEMO variables averaged over depth layers, one panel per layer",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    add_common_arguments(parser)
    parser.add_argument("--layers", nargs="+", type=float, metavar="Z",
                        help="Layer interfaces [m], e.g. '0 700 2000' gives 0-700, 700-2000, 2000-bottom "
                             "(the full column is always added). Default: 0 100 300 700 2000")
    parser.add_argument("--mode", default="plain", choices=MODES,
                        help="Time mean: plain (monthly), yearly, monthly/seasonally (seasonal cycle)")
    parser.add_argument("--moving", action="store_true", help="Apply a 12-month moving average (mode=plain only)")
    parser.add_argument("--rescale", action="store_true", help="Rescale each series by its initial value")
    parser.add_argument("--timeoff", type=float, default=0, help="Offset added to the time axis")

    parsed = parser.parse_args(argv)
    check_common_arguments(parser, parsed)

    if parsed.moving and parsed.mode != "plain":
        parser.error("--moving requires --mode plain")

    if parsed.layers is None:
        parsed.layers = LAYERS
    else:
        z = parsed.layers
        if any(z2 <= z1 for z1, z2 in zip(z[:-1], z[1:])) or z[0] < 0:
            parser.error("--layers must be non-negative and increasing")
        parsed.layers = list(zip(z[:-1], z[1:])) + [(z[-1], None), (0, None)]

    return parsed


def main(argv=None):

    # parser
    args = parse_args(argv)
    logging.getLogger().setLevel(logging.INFO)

    # figures go in the post folder of the first experiment
    postdir = get_postdir(args.exps, config_path=args.config_file)

    avetype = "moving" if args.moving else "standard"
    marker = "o" if args.mode in ("monthly", "seasonally") else None
    npanels = len(args.layers)
    ncols = 2 if npanels <= 4 else 3
    nrows = -(-npanels // ncols)

    varlist = catalogue.observables('nemo')
    produced, failed = [], []
    for varname in args.vars:

        if varname not in varlist:
            logging.error(f"Unknown variable '{varname}': skipped")
            failed.append((varname, "unknown variable"))
            continue
        try:
            check_diagnostic(varname, 'hovmoller')
        except ValueError as e:
            logging.error(f"Skipping {varname}: {e}")
            failed.append((varname, "layers needs a 3D variable"))
            continue
        info = varlist[varname]

        fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.5 * nrows), sharex=True, squeeze=False)
        axes = axes.ravel()
        for ax in axes[npanels:]:
            ax.set_visible(False)

        nplotted = 0
        for exp, label in zip(args.exps, args.labels):
            try:
                plot_timeseries_by_layers(exp["expname"], exp["startyear"], exp["endyear"], varname,
                                          layers=args.layers, mode=args.mode, reader="post", orca=args.orca,
                                          replace=args.replace, metric=args.metric, refinfo=args.refinfo,
                                          config_path=args.config_file, rescale=args.rescale, avetype=avetype,
                                          timeoff=args.timeoff, marker=marker, label=label, axes=axes[:npanels])
                nplotted += 1
            except Exception as e:
                logging.exception(f"Failed to plot {varname} for {exp['expname']}: {e}")
                failed.append((f"{varname} {exp['expname']}", str(e)))

        if nplotted == 0:
            plt.close(fig)
            continue

        # figure settings: x label on the bottom row, y label on the first column
        xlabels = {"plain": "time [years]", "yearly": "time [years]", "monthly": "month", "seasonally": "season"}
        ylabel = info['long_name'] if args.rescale else f"{info['long_name']} [{info['units']}]"
        if args.metric != "base":
            ylabel = f"{ylabel} ({args.metric} vs {args.refinfo['expname']})"
        for i, ax in enumerate(axes[:npanels]):
            ax.set_xlabel(xlabels[args.mode] if i + ncols >= npanels else "")
            ax.set_ylabel(ylabel if i % ncols == 0 else "")
            ax.tick_params(labelbottom=True)
            if args.mode != "seasonally":
                ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.grid(alpha=0.3)
        axes[0].legend()
        fig.suptitle(f"{varname} timeseries by layers" + (f" ({args.mode})" if args.mode != "plain" else ""))
        fig.tight_layout()

        suffixes = [args.mode if args.mode != "plain" else None, "movave" if args.moving else None]
        figname = get_figure_path(postdir, args.exps, varname, "layers", suffixes=suffixes,
                                  metric=args.metric, fmt=args.fmt)
        fig.savefig(figname, dpi=args.dpi)
        plt.close(fig)
        produced.append(figname)

    return print_summary(produced, failed)


if __name__ == "__main__":
    sys.exit(main())
