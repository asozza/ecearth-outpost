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

logging.basicConfig(
    #filename='logfile.log',
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    """ Load configuration file """

    config_path = "../../config.yml"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

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

