#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Folder definitions

Author: Alessandro Sozza (CNR-ISAC)
Date: Mar 2024
"""

import os
import yaml
import logging
import platform

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_project_root(project_name="ecearth-outpost"):
    """ Get base folder of the github project (anchored to this file's location) """

    this_file = os.path.abspath(__file__)
    parts = this_file.split(os.sep)

    if project_name in parts:
        idx = parts.index(project_name)
        root = os.sep.join(parts[:idx+1])
        return root

    raise RuntimeError(f"Folder '{project_name}' not found in path: {this_file}")


def load_config():
    """ Load configuration file """

    project_root = get_project_root()
    config_path = os.path.join(project_root, "config.yml")

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    logging.warning(f"Config file not found at path: {config_path}. Using empty config.")

    return {}
    

def folders(expname):
    """ List of global paths dependent on expname """
    
    system = platform.system().lower()
    config = load_config()
    config = config.get(system)    
    base_path = config.get("base_path")
    src_path = config.get("src_path")
    data_path = config.get("data_path")

    if expname == "":
        dirs = {
            'rebuild': os.path.join(src_path, "rebuild_nemo"),
            'domain': os.path.join(data_path, "nemo", "domain")
        }
    else:
        dirs = {
            'exp': os.path.join(base_path, expname),
            'nemo': os.path.join(base_path, expname, "output", "nemo"),
            'oifs': os.path.join(base_path, expname, "output", "oifs"),
            'restart': os.path.join(base_path, expname, "restart"),
            'log': os.path.join(base_path, expname, "log"),
            'tmp': os.path.join(base_path, expname, "tmp"),
            'post': os.path.join(base_path, expname, "post"),
            'rebuild': os.path.join(src_path, "rebuild_nemo"),
            'domain': os.path.join(data_path, "nemo", "domain")
        }
        
        # Create 'post' & 'tmp' folder if it doesn't exist
        os.makedirs(dirs['post'], exist_ok=True)
        os.makedirs(dirs['tmp'], exist_ok=True)

    return dirs

