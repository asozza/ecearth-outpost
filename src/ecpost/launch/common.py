#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Shared pieces of the plotting command line tools (timeseries, profile, ...):
experiments definition, reference climatology, output folder and figure names.

With more experiments in the same figure, the first one defines the workspace:
figures are written in its 'post' folder.

Authors: Alessandro Sozza (CNR-ISAC)
Date: Oct 2026
"""

import os

from ecpost.utils.config import Config


def add_common_arguments(parser):
    """Add the arguments shared by all plotting tools"""

    parser.add_argument("-e", "--exp", dest="exps", nargs=3, action="append", required=True,
                        metavar=("EXPNAME", "STARTYEAR", "ENDYEAR"),
                        help="Experiment and time window (repeat for more experiments in the same plot; "
                             "the first one defines the output folder)")
    parser.add_argument("-v", "--vars", nargs="+", required=True, metavar="VAR", help="NEMO variable names (see catalogue)")
    parser.add_argument("--labels", nargs="+", metavar="LABEL", help="Legend labels, one per experiment (default: expname)")
    parser.add_argument("--orca", default="ORCA2", help="ORCA configuration [ORCA2, eORCA1]")
    parser.add_argument("--config", dest="config_file", default=None, help="Configuration file (default: ./config.yml)")
    parser.add_argument("--metric", default="base", help="Metric with respect to the reference climatology [base, diff, ...]")
    parser.add_argument("--ref", nargs=3, metavar=("REFEXP", "REFSTART", "REFEND"), help="Reference experiment and time window (needed by --metric)")
    parser.add_argument("--replace", action="store_true", help="Recompute and replace existing aggregated files")
    parser.add_argument("--format", dest="fmt", default="png", help="Figure format [png, pdf, ...]")
    parser.add_argument("--dpi", type=int, default=150, help="Figure resolution")


def check_common_arguments(parser, parsed):
    """Validate the shared arguments; set parsed.exps (list of dicts), parsed.labels and parsed.refinfo"""

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

    if parsed.labels is None:
        parsed.labels = [e["expname"] for e in exps]
    elif len(parsed.labels) != len(exps):
        parser.error("--labels must have one label per experiment")

    if parsed.metric != "base" and parsed.ref is None:
        parser.error("--metric requires --ref REFEXP REFSTART REFEND")
    parsed.refinfo = None
    if parsed.ref is not None:
        try:
            parsed.refinfo = {"expname": parsed.ref[0], "startyear": int(parsed.ref[1]), "endyear": int(parsed.ref[2])}
        except ValueError:
            parser.error("--ref: REFSTART and REFEND must be integers")

    return parsed


def get_postdir(exps, config_path=None):
    """Output folder: 'post' folder of the first experiment"""

    config = Config(config_path=config_path)
    return config.folders(exps[0]["expname"])['post']


def get_figure_path(postdir, exps, varname, diagname, suffixes=(), metric="base", fmt="png"):
    """
    get figure file path:
    <expname1>[-<expname2>...]_<startyear>-<endyear>_<varname>_<diagname>[_<suffix>...][_<metric>].<fmt>
    where the time window spans all the experiments
    """

    expnames = "-".join(e["expname"] for e in exps)
    startyear = min(e["startyear"] for e in exps)
    endyear = max(e["endyear"] for e in exps)
    suffix = "".join(f"_{s}" for s in suffixes if s)
    suffix += f"_{metric}" if metric != "base" else ""
    filename = f"{expnames}_{startyear}-{endyear}_{varname}_{diagname}{suffix}.{fmt}"

    return os.path.join(postdir, filename)


def print_summary(produced, failed):
    """Print produced figures and failures; return the exit code"""

    print("\nSummary:")
    for f in produced:
        print(f"  [ok]   {f}")
    for name, err in failed:
        print(f"  [fail] {name}: {err}")

    return 1 if failed else 0
