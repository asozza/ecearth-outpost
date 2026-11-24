#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command line tool to plot Hovmoller diagrams (horizontal mean as function of time and depth)
of 3D NEMO variables for one or more EC-Earth4 experiments. Data are read from the aggregated
'hovmoller' diagnostic (produced on the fly if missing, see climatology). Each experiment gets
its own panel, with a common time axis and color scale. One figure per variable is written in
the 'post' folder of the first experiment (see launch/common.py) as
<expname1>[-<expname2>...]_<startyear>-<endyear>_<varname>_hovmoller[_<mode>][_<metric>].<fmt>

Examples:
    hovmoller -e cs00 1990 1999 -v thetao so
    hovmoller -e cs00 1990 1999 -e cs01 1990 2009 -v thetao --mode yearly --zmax 1000
    hovmoller -e cs01 1990 1999 -v thetao --metric diff --ref cs00 1990 1999 --config config.yml

Authors: Alessandro Sozza (CNR-ISAC)
Date: Oct 2026
"""

import argparse
import logging
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cmocean  # noqa: F401, registers the cmo.* colormaps

from ecpost.utils import catalogue
from ecpost.io.postreader import check_diagnostic
from ecpost.graphics.hovmoller import plot_hovmoller
from ecpost.launch.common import (add_common_arguments, add_color_arguments, check_common_arguments, get_postdir,
                                  get_figure_path, shared_limits, print_summary)

MODES = ["plain", "yearly"]


def parse_args(argv=None):
    """Command line parser for hovmoller"""

    parser = argparse.ArgumentParser(
        description="Plot Hovmoller diagrams (time x depth) of 3D NEMO variables for one or more experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    add_common_arguments(parser)
    add_color_arguments(parser)
    parser.add_argument("--mode", default="plain", choices=MODES, help="Time mean: plain (monthly), yearly")
    parser.add_argument("--zmax", type=float, default=5000, help="Maximum depth shown [m] (default: 5000)")
    parser.add_argument("--rescale", action="store_true", help="Rescale each level by its initial value")
    parser.add_argument("--timeoff", type=float, default=0, help="Offset added to the time axis")

    parsed = parser.parse_args(argv)
    check_common_arguments(parser, parsed)

    if parsed.zmax <= 0:
        parser.error("--zmax must be positive")

    return parsed


def main(argv=None):

    # parser
    args = parse_args(argv)
    logging.getLogger().setLevel(logging.INFO)

    # figures go in the post folder of the first experiment
    postdir = get_postdir(args.exps, config_path=args.config_file)

    anomaly = args.metric != "base"
    cmap = args.cmap or ("cmo.balance" if anomaly else "RdYlBu_r")
    nexps = len(args.exps)

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
            failed.append((varname, "hovmoller needs a 3D variable"))
            continue
        info = varlist[varname]

        fig, axes = plt.subplots(nexps, 1, figsize=(11, 3.5 * nexps + 0.5), sharex=True, sharey=True, squeeze=False)
        axes = axes[:, 0]
        meshes = []
        for ax, exp, label in zip(axes, args.exps, args.labels):
            try:
                pp = plot_hovmoller(exp["expname"], exp["startyear"], exp["endyear"], varname, mode=args.mode,
                                    reader="post", orca=args.orca, replace=args.replace, metric=args.metric,
                                    refinfo=args.refinfo, config_path=args.config_file, rescale=args.rescale,
                                    timeoff=args.timeoff, zmax=args.zmax, ax=ax, cmap=cmap)
                meshes.append(pp)
                ax.set_title(label)
            except Exception as e:
                logging.exception(f"Failed to plot {varname} for {exp['expname']}: {e}")
                failed.append((f"{varname} {exp['expname']}", str(e)))
                ax.set_title(f"{label}: not available")

        if not meshes:
            plt.close(fig)
            continue

        # common color scale
        vmin, vmax = shared_limits([pp.get_array() for pp in meshes], args.vmin, args.vmax, symmetric=anomaly)
        for pp in meshes:
            pp.set_clim(vmin, vmax)

        # figure settings
        cbar_label = info['long_name'] if args.rescale else f"{info['long_name']} [{info['units']}]"
        if anomaly:
            cbar_label = f"{cbar_label} ({args.metric} vs {args.refinfo['expname']})"
        for ax in axes[:-1]:
            ax.set_xlabel("")
        fig.suptitle(f"{varname} hovmoller" + (f" ({args.mode})" if args.mode != "plain" else ""))
        fig.colorbar(meshes[0], ax=list(axes), label=cbar_label, extend="both", shrink=0.9)

        suffixes = [args.mode if args.mode != "plain" else None]
        figname = get_figure_path(postdir, args.exps, varname, "hovmoller", suffixes=suffixes,
                                  metric=args.metric, fmt=args.fmt)
        fig.savefig(figname, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        produced.append(figname)

    return print_summary(produced, failed)


if __name__ == "__main__":
    sys.exit(main())
