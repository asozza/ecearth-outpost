#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command line tool to plot horizontal maps of NEMO variables, averaged over the time window,
for one or more EC-Earth4 experiments. By default the aggregated 'map' diagnostic is used
(vertical mean for 3D variables); with --depth a single model level is taken from the 'field'
diagnostic. Both are produced on the fly if missing (see climatology). Each experiment gets its
own panel, with a common color scale. One figure per variable is written in the 'post' folder
of the first experiment (see launch/common.py) as
<expname1>[-<expname2>...]_<startyear>-<endyear>_<varname>_map[_z<depth>][_<metric>].<fmt>

Examples:
    map -e cs00 1990 1999 -v tos sos
    map -e cs00 1990 1999 -e cs01 1990 2009 -v thetao --depth 100
    map -e cs01 1990 1999 -v tos --metric diff --ref cs00 1990 1999 --config config.yml

Authors: Alessandro Sozza (CNR-ISAC)
Date: Oct 2026
"""

import argparse
import logging
import math
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import QuadMesh
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean  # noqa: F401, registers the cmo.* colormaps

from ecpost.utils import catalogue
from ecpost.graphics.map import read_map, plot_map
from ecpost.launch.common import (add_common_arguments, add_color_arguments, check_common_arguments, get_postdir,
                                  get_figure_path, shared_limits, print_summary)

PROJECTIONS = {
    "robinson": ccrs.Robinson,
    "platecarree": ccrs.PlateCarree,
    "mollweide": ccrs.Mollweide,
}


def parse_args(argv=None):
    """Command line parser for map"""

    parser = argparse.ArgumentParser(
        description="Plot horizontal maps (time mean over the window) of NEMO variables for one or more experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    add_common_arguments(parser)
    add_color_arguments(parser)
    parser.add_argument("--depth", type=float, default=None,
                        help="Depth [m] of the model level to plot, 3D variables only (default: vertical mean)")
    parser.add_argument("--projection", default="robinson", choices=list(PROJECTIONS), help="Map projection")

    parsed = parser.parse_args(argv)
    check_common_arguments(parser, parsed)

    if parsed.depth is not None and parsed.depth < 0:
        parser.error("--depth must be >= 0")

    return parsed


def main(argv=None):

    # parser
    args = parse_args(argv)
    logging.getLogger().setLevel(logging.INFO)

    # shapely complains about the land (NaN) cells of the ORCA grid when cartopy wraps them
    warnings.filterwarnings("ignore", message="invalid value encountered in create_collection")

    # figures go in the post folder of the first experiment
    postdir = get_postdir(args.exps, config_path=args.config_file)

    anomaly = args.metric != "base"
    cmap = args.cmap or ("cmo.balance" if anomaly else "RdYlBu_r")
    projection = PROJECTIONS[args.projection]()

    # panel layout: one column for a single experiment, two otherwise
    nexps = len(args.exps)
    ncols = 1 if nexps == 1 else 2
    nrows = math.ceil(nexps / ncols)

    varlist = catalogue.observables('nemo')
    produced, failed = [], []
    for varname in args.vars:

        if varname not in varlist:
            logging.error(f"Unknown variable '{varname}': skipped")
            failed.append((varname, "unknown variable"))
            continue
        info = varlist[varname]
        if args.depth is not None and info['dim'] != '3D':
            logging.error(f"Skipping {varname}: --depth requires a 3D variable")
            failed.append((varname, "--depth requires a 3D variable"))
            continue

        # read all experiments first, to define a common color scale
        fields = []
        for exp, label in zip(args.exps, args.labels):
            try:
                data = read_map(exp["expname"], exp["startyear"], exp["endyear"], varname, depth=args.depth,
                                orca=args.orca, replace=args.replace, metric=args.metric, refinfo=args.refinfo,
                                config_path=args.config_file)
                fields.append((label, data))
            except Exception as e:
                logging.exception(f"Failed to read {varname} for {exp['expname']}: {e}")
                failed.append((f"{varname} {exp['expname']}", str(e)))

        if not fields:
            continue

        vmin, vmax = shared_limits([data.values for _, data in fields], args.vmin, args.vmax, symmetric=anomaly)

        fig, axes = plt.subplots(nrows, ncols, figsize=(8 * ncols, 5 * nrows + 0.8),
                                 subplot_kw={"projection": projection}, squeeze=False,
                                 gridspec_kw={"hspace": 0.3, "wspace": 0.15})
        axes = axes.flatten()
        mesh = None
        for ax, (label, data) in zip(axes, fields):
            plot_map(data, data['lon'], data['lat'], ax=ax, projection=projection, title=label,
                     cmap=cmap, colorbar=False, vmin=vmin, vmax=vmax)
            mesh = next(c for c in ax.collections if isinstance(c, QuadMesh))
            ax.add_feature(cfeature.LAND, facecolor="lightgray", zorder=1)
        for ax in axes[len(fields):]:
            ax.remove()

        # figure settings
        cbar_label = f"{info['long_name']} [{info['units']}]"
        if anomaly:
            cbar_label = f"{cbar_label} ({args.metric} vs {args.refinfo['expname']})"
        if args.depth is not None:
            depth = float(fields[0][1]['z']) if 'z' in fields[0][1].coords else args.depth
            title = f"{varname} at {depth:.0f} m"
        else:
            title = f"{varname} vertical mean" if info['dim'] == '3D' else varname
        fig.suptitle(title, fontsize=15)
        fig.colorbar(mesh, ax=list(axes[:len(fields)]), orientation="horizontal",
                     label=cbar_label, extend="both", shrink=0.6, pad=0.06)

        suffixes = [f"z{args.depth:g}" if args.depth is not None else None]
        figname = get_figure_path(postdir, args.exps, varname, "map", suffixes=suffixes,
                                  metric=args.metric, fmt=args.fmt)
        fig.savefig(figname, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        produced.append(figname)

    return print_summary(produced, failed)


if __name__ == "__main__":
    sys.exit(main())
