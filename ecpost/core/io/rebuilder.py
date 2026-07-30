#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rebuilder

Authors: Alessandro Sozza (CNR-ISAC) 
Date: Oct 2023
"""

import os
import glob
import subprocess

from ecpost.core.utils.config import Config

cfg = Config()

def _get_nemo_timestep(filename):
    """ Get timestep from a NEMO restart file """

    return os.path.basename(filename).split('_')[1]

##########################################################################################

def rebuild_nemo_restart(expname, leg):
    """Function to rebuild NEMO restart """

    dirs = cfg.folders(expname)
    
    os.makedirs(os.path.join(dirs['tmp'], str(leg).zfill(3)), exist_ok=True)

    rebuild_exe = os.path.join(dirs['rebuild'], "rebuild_nemo")
  
    for kind in ['restart', 'restart_ice']:
        print(' Processing ' + kind)
        flist = glob.glob(os.path.join(dirs['restart'], str(leg).zfill(3), expname + '*_' + kind + '_????.nc'))        
        tstep = _get_nemo_timestep(flist[0])

        for filename in flist:
            destination_path = os.path.join(dirs['tmp'], str(leg).zfill(3), os.path.basename(filename))
            try:
                os.symlink(filename, destination_path)
            except FileExistsError:
                pass

        rebuild_command = [rebuild_exe, "-m", os.path.join(dirs['tmp'], str(leg).zfill(3), expname + "_" + tstep + "_" + kind ), str(len(flist))]
        try:
            print(rebuild_command)
            subprocess.run(rebuild_command, stderr=subprocess.PIPE, text=True, check=True)
            for file in glob.glob('nam_rebuld_*'):
                os.remove(file)
        except subprocess.CalledProcessError as e:
            error_message = e.stderr
            print(error_message)

        for filename in flist:
            destination_path = os.path.join(dirs['tmp'], str(leg).zfill(3), os.path.basename(filename))
            os.remove(destination_path)

    # copy restart
    #tstep = _get_nemo_timestep(glob.glob(os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '*_restart.nc'))[0])
    #shutil.copy(os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '_' + tstep + '_restart.nc'), os.path.join(dirs['tmp'], str(leg).zfill(3), 'restart.nc'))
    #shutil.copy(os.path.join(dirs['tmp'], str(leg).zfill(3), expname + '_' + tstep + '_restart_ice.nc'), os.path.join(dirs['tmp'], str(leg).zfill(3), 'restart_ice.nc'))

    # delete temporary files
    flist = glob.glob('nam_rebuild*')
    for file in flist:
        os.remove(file)

    return None
