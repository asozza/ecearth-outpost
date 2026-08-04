#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is a command line tool to modfy the NEMO restart files from a specific EC-Eart4
experiment, given a specific experiment and leg. 

Needed modules:
# module load intel/2021.4.0 intel-mkl/19.0.5 prgenv/intel hdf5 netcdf4 
# export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/apps/netcdf4/4.9.1/INTEL/2021.4/lib:/usr/local/apps/hdf5/1.12.2/INTEL/2021.4/lib

Authors: Alessandro Sozza (CNR-ISAC)
Date: May 2024
"""

import argparse
import logging
import sys
import datetime
import os
import xarray as xr

from ecpost.core.utils.config import Config
from ecpost.core.io.postreader import get_climatology

def parse_args():
    """Command line parser for nemo-restart"""

    parser = argparse.ArgumentParser(description="Command Line Parser for nemo-restart")

    # add positional argument (mandatory)
    parser.add_argument("expname", metavar="EXPNAME", help="Experiment name")
    parser.add_argument("endyear", metavar="ENDYEAR", help="Ending year", type=int)
    parser.add_argument("window", metavar="WINDOW", help="EOF window", type=int)
    parser.add_argument("years_to_skip", metavar="YEARS_TO_SKIP", help="Years to skip", type=int)
    parser.add_argument("config_file", metavar="CONFIG_FILE", help="Configuration file", type=str)

    # optional to activate nemo rebuild
    parser.add_argument("--rebuild", action="store_true", help="Enable nemo-rebuild")
    parser.add_argument("--forecast", action="store_true", help="Create forecast")
    #parser.add_argument("--mode", choices=['first', 'full', 'other'], default='full', help="Mode for processing")
    #parser.add_argument("--replace", action="store_true", help="Replace nemo restart files")
    #parser.add_argument("--restore", action="store_true", help="Restore nemo restart files")

    parsed = parser.parse_args()

    return parsed


if __name__ == "__main__":
    
    # parser
    args = parse_args()
    expname = args.expname
    endyear = args.endyear
    window = args.window
    years_to_skip = args.years_to_skip
    config_file = args.config_file

    # define folders
    config = Config(args.config_file)
    dirs = config.folders(expname)

    get_climatology(expname='cs00', startyear=6069, endyear=6999, varname='thetao')