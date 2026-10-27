#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command line tool to plot the timeseries (surface/volume mean) of NEMO variables for one or
more EC-Earth4 experiments in the same figure. Data are read from the aggregated 'timeseries'
diagnostic (produced on the fly if missing, see climatology). One figure per variable is
written in the 'post' folder of the first experiment as
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
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ecpost.utils import catalogue
from ecpost.utils.config import Config
from ecpost.graphics.timeseries import plot_timeseries

MODES = ["plain", "yearly", "monthly", "seasonally"]


def parse_args(argv=None):
    """Command line parser for timeseries"""

    parser = argparse.ArgumentParser(
        description="Plot timeseries (surface/volume mean) of NEMO variables for one or more experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-e", "--exp", dest="exps", nargs=3, action="append", required=True,
                        metavar=("EXPNAME", "STARTYEAR", "ENDYEAR"),
                        help="Experiment and time window (repeat for more experiments in the same plot)")
    parser.add_argument("-v", "--vars", nargs="+", required=True, metavar="VAR", help="NEMO variable names (see catalogue)")
    parser.add_argument("--mode", default="plain", choices=MODES,
                        help="Time mean: plain (monthly), yearly, monthly/seasonally (seasonal cycle)")
    parser.add_argument("--moving", action="store_true", help="Apply a 12-month moving average (mode=plain only)")
    parser.add_argument("--rescale", action="store_true", help="Rescale each series by its initial value")
    parser.add_argument("--timeoff", type=float, default=0, help="Offset added to the time axis")
    parser.add_argument("--labels", nargs="+", metavar="LABEL", help="Legend labels, one per experiment (default: expname)")
    parser.add_argument("--orca", default="ORCA2", help="ORCA configuration [ORCA2, eORCA1]")
    parser.add_argument("--config", dest="config_file", default=None, help="Configuration file (default: ./config.yml)")
    parser.add_argument("--metric", default="base", help="Metric with respect to the reference climatology [base, diff, ...]")
    parser.add_argument("--ref", nargs=3, metavar=("REFEXP", "REFSTART", "REFEND"), help="Reference experiment and time window (needed by --metric)")
    parser.add_argument("--replace", action="store_true", help="Recompute and replace existing aggregated files")
    parser.add_argument("--format", dest="fmt", default="png", help="Figure format [png, pdf, ...]")
    parser.add_argument("--dpi", type=int, default=150, help="Figure resolution")

    parsed = parser.parse_args(argv)

    exps = []
    for expname, startyear, endyear in parsed.exps:
        try:
            startyear, endyear = int(startyear), int(endyear)
        except ValueError:
            parser.error(f"-e {expname} {startyear} {endyear}: STARTYEAR and ENDYEAR must be integers")
        if endyear < startyear:
            parser.error(f"-e {expname}: ENDYEAR must be >= STARTYEAR")
        exps.append({"expname": expname, "startyear": startyear, "endyear": endyear})
    parsed.exps = exps

    if parsed.labels is not None and len(parsed.labels) != len(parsed.exps):
        parser.error("--labels must have one label per experiment")
    if parsed.moving and parsed.mode != "plain":
        parser.error("--moving requires --mode plain")
    if parsed.metric != "base" and parsed.ref is None:
        parser.error("--metric requires --ref REFEXP REFSTART REFEND")

    return parsed


def get_figure_path(postdir, exps, varname, mode="plain", moving=False, metric="base", fmt="png"):
    """get figure file path"""

    expnames = "-".join(e["expname"] for e in exps)
    startyear = min(e["startyear"] for e in exps)
    endyear = max(e["endyear"] for e in exps)
    suffix = f"_{mode}" if mode != "plain" else ""
    suffix += "_movave" if moving else ""
    suffix += f"_{metric}" if metric != "base" else ""
    filename = f"{expnames}_{startyear}-{endyear}_{varname}_timeseries{suffix}.{fmt}"

    return os.path.join(postdir, filename)


def main(argv=None):

    # parser
    args = parse_args(argv)
    logging.getLogger().setLevel(logging.INFO)

    refinfo = None
    if args.ref is not None:
        refinfo = {"expname": args.ref[0], "startyear": int(args.ref[1]), "endyear": int(args.ref[2])}

    # figures go in the post folder of the first experiment
    config = Config(config_path=args.config_file)
    dirs = config.folders(args.exps[0]["expname"])

    labels = args.labels or [e["expname"] for e in args.exps]
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
        for exp, label in zip(args.exps, labels):
            try:
                plot_timeseries(exp["expname"], exp["startyear"], exp["endyear"], varname, mode=args.mode,
                                reader="post", orca=args.orca, replace=args.replace, metric=args.metric,
                                refinfo=refinfo, config_path=args.config_file, rescale=args.rescale,
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
            ylabel = f"{ylabel} ({args.metric} vs {refinfo['expname']})"
        ax.set_ylabel(ylabel)
        ax.set_title(f"{varname} timeseries" + (f" ({args.mode})" if args.mode != "plain" else ""))
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()

        figname = get_figure_path(dirs['post'], args.exps, varname, mode=args.mode, moving=args.moving,
                                  metric=args.metric, fmt=args.fmt)
        fig.savefig(figname, dpi=args.dpi)
        plt.close(fig)
        produced.append(figname)

    print("\nSummary:")
    for f in produced:
        print(f"  [ok]   {f}")
    for name, err in failed:
        print(f"  [fail] {name}: {err}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
