#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Domain module

Author: Alessandro Sozza (CNR-ISAC)
Date: June 2024
"""

import os
import logging
import functools
import xarray as xr

from ecpost.utils.config import Config

##########################################################################################
# Reader of NEMO domain

def preproc_nemo_domain(data):
    """ Pre-processing routine for nemo domain: drop the singleton time axis """

    # domain_cfg.nc may use 't', 'time_counter' or 'time' as (singleton) time dimension
    for dim in ('t', 'time_counter', 'time'):
        if dim in data.dims:
            data = data.isel({dim: 0})
    for var in ('time_counter', 'time'):
        if var in data.variables:
            data = data.drop_vars(var)

    return data

def read_domain(orca='ORCA2', config_path=None):
    """ Read NEMO domain configuration file """

    # configure folders
    cfg = Config(config_path=config_path)
    dirs = cfg.folders("")

    filename = os.path.join(dirs['domain'], orca, 'domain_cfg.nc')
    domain = xr.open_dataset(filename)
    domain = preproc_nemo_domain(domain)

    return domain

@functools.lru_cache(maxsize=4)
def elements(orca='ORCA2', config_path=None):
    """ Define differential forms for integrals (cached: the domain is read once per grid) """

    df = {}
    domain = read_domain(orca, config_path=config_path).load()
    df['V'] = domain['e1t']*domain['e2t']*domain['e3t_0']
    df['S'] = domain['e1t']*domain['e2t']
    df['x'] = domain['e1t']
    df['y'] = domain['e2t']
    df['z'] = domain['e3t_0']

    # wet volume of each level (horizontal means of 3D fields are combined with these weights)
    level = xr.DataArray(range(1, domain.sizes['z'] + 1), dims='z')
    tmask = (level >= domain['top_level']) & (level <= domain['bottom_level']) & (domain['top_level'] > 0)
    df['Vz'] = df['V'].where(tmask, 0).sum(dim=['y', 'x'])

    return df

##########################################################################################
