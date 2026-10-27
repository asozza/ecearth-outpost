#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command line tool to plot vertical profiles (horizontal mean) of 3D NEMO variables for one or
more EC-Earth4 experiments in the same figure. Data are read from the aggregated 'hovmoller'
diagnostic (produced on the fly if missing, see climatology). Profiles are averaged over the
time window (mode global, one panel) or by month/season (one panel per month/season).
One figure per variable is written in the 'post' folder of the first experiment
(see launch/common.py) as
<expname1>[-<expname2>...]_<startyear>-<endyear>_<varname>_profile[_<mode>][_<metric>].<fmt>

Examples:
    profile -e cs00 1990 1999 -v thetao so
    profile -e cs00 1990 1999 -e cs01 1990 2009 -v thetao --zmax 1000 --labels control warming
    profile -e cs00 1990 1999 -e cs01 1990 1999 -v thetao --mode seasonally
    profile -e cs01 1990 1999 -v thetao --metric diff --ref cs00 1990 1999 --config config.yml

Authors: Alessandro Sozza (CNR-ISAC)
Date: Oct 2026
"""

import argparse
import logging
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ecpost.utils import catalogue
from ecpost.io.postreader import check_diagnostic
from ecpost.graphics.profile import plot_profile
from ecpost.launch.common import add_common_arguments, check_common_arguments, get_postdir, get_figure_path, print_summary

# mode -> (periods, panel layout)
MODES = {
    "global":     ([None], (1, 1)),
    "seasonally": (["DJF", "MAM", "JJA", "SON"], (2, 2)),
    "monthly":    (list(range(1, 13)), (3, 4)),
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _limit_depth(ax, zmax):
    """ Show depths down to zmax and rescale the x axis on the visible part of the profiles """

    ax.set_ylim(-zmax, 0)
    visible = [line.get_xdata()[line.get_ydata() >= -zmax] for line in ax.get_lines()]
    visible = np.concatenate([v for v in visible if v.size]) if any(v.size for v in visible) else np.array([])
    visible = visible[np.isfinite(visible)]
    if visible.size:
        pad = 0.05 * (visible.max() - visible.min()) or 0.5
        ax.set_xlim(visible.min() - pad, visible.max() + pad)


def parse_args(argv=None):
    """Command line parser for profile"""

    parser = argparse.ArgumentParser(
        description="Plot vertical profiles (horizontal mean) of 3D NEMO variables for one or more experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    add_common_arguments(parser)
    parser.add_argument("--mode", default="global", choices=list(MODES),
                        help="Time mean: global (over the window, one panel), seasonally (4 panels), monthly (12 panels)")
    parser.add_argument("--zmax", type=float, default=None, help="Maximum depth shown [m]")

    parsed = parser.parse_args(argv)
    check_common_arguments(parser, parsed)

    if parsed.zmax is not None and parsed.zmax <= 0:
        parser.error("--zmax must be positive")

    return parsed


def main(argv=None):

    # parser
    args = parse_args(argv)
    logging.getLogger().setLevel(logging.INFO)

    # figures go in the post folder of the first experiment
    postdir = get_postdir(args.exps, config_path=args.config_file)

    periods, (nrows, ncols) = MODES[args.mode]

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
            failed.append((varname, "profiles need a 3D variable"))
            continue
        info = varlist[varname]

        fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols + 1, 5 * nrows), sharey=True, squeeze=False)
        axes = axes.flatten()
        nplotted = 0
        for exp, label in zip(args.exps, args.labels):
            try:
                for ax, period in zip(axes, periods):
                    plot_profile(exp["expname"], exp["startyear"], exp["endyear"], varname, mode=args.mode,
                                 period=period, reader="post", orca=args.orca, replace=args.replace,
                                 metric=args.metric, refinfo=args.refinfo, config_path=args.config_file,
                                 label=label, ax=ax)
                nplotted += 1
            except Exception as e:
                logging.exception(f"Failed to plot {varname} for {exp['expname']}: {e}")
                failed.append((f"{varname} {exp['expname']}", str(e)))

        if nplotted == 0:
            plt.close(fig)
            continue

        # figure settings
        xlabel = f"{info['long_name']} [{info['units']}]"
        if args.metric != "base":
            xlabel = f"{xlabel} ({args.metric} vs {args.refinfo['expname']})"
        for i, (ax, period) in enumerate(zip(axes, periods)):
            ax.set_xlabel(xlabel if i >= len(periods) - ncols else "")
            ax.set_ylabel("depth [m]" if i % ncols == 0 else "")
            if period is not None:
                ax.set_title(MONTHS[period - 1] if args.mode == "monthly" else period)
            if args.zmax is not None:
                _limit_depth(ax, args.zmax)
            if args.metric != "base":
                ax.axvline(0, color='gray', linestyle='--', linewidth=0.8)
            ax.grid(alpha=0.3)
        axes[0].legend()
        fig.suptitle(f"{varname} profile" + (f" ({args.mode})" if args.mode != "global" else ""))
        fig.tight_layout()

        suffixes = [args.mode if args.mode != "global" else None]
        figname = get_figure_path(postdir, args.exps, varname, "profile", suffixes=suffixes,
                                  metric=args.metric, fmt=args.fmt)
        fig.savefig(figname, dpi=args.dpi)
        plt.close(fig)
        produced.append(figname)

    return print_summary(produced, failed)


if __name__ == "__main__":
    sys.exit(main())
