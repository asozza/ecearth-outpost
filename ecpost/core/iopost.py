#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
post I/O module

Author: Alessandro Sozza (CNR-ISAC)
Date: Nov 2025
"""

import os
import logging
import numpy as np
import xarray as xr

from ecpost.core import config
from ecpost.core import catalogue   
from ecpost.core.io import reader_nemo_field
from ecpost.core.means import spacemean, timemean, apply_cost_function

# dask optimization of blocksizes
#dask.config.set({'array.optimize_blockwise': True})

# dictionary of months by seasons
season_months = {"DJF": [12, 1, 2], "MAM": [3, 4, 5], "JJA": [6, 7, 8], "SON": [9, 10, 11]}

def _update_description(data, refinfo):

    description = data.attrs.get('description', 'No description')
    if 'refinfo' in locals() and isinstance(refinfo, dict):
        refinfo_str = ', '.join([f"{key}: {value}" for key, value in refinfo.items()])
        description += f" {refinfo_str}"
    data.attrs['description'] = description

    return data

##########################################################################################
# Reader for averaged data

def reader_averaged(expname, startyear, endyear, varname, diagname, format, metric, refinfo):
    """ 
    Reader of averaged data 
    
    Args:
    expname: experiment name
    startyear,endyear: time window
    varname: variable name
    diagname: diagnostics name [series, prof, hovm, map, fld, pdf]
    format: time format [plain, global, monthly, seasonally, yearly]
    metric: tag indicating the type of cost function [base, diff, var, rel, ...]
    
    """

    dirs = config.folders(expname)

    filename = f"{varname}_{expname}_{startyear}-{endyear}_{diagname}_{format}_{metric}"
    if metric != 'base':
        filename += f"_{refinfo['expname']}_{refinfo['startyear']}-{refinfo['endyear']}_{refinfo['diagname']}_{refinfo['format']}"
    filename = os.path.join(dirs['post'], f"{filename}.nc")

    logging.info('File to be loaded %s', filename)
    data = xr.open_dataset(filename, use_cftime=True)
    
    return data


def writer_averaged(data, expname, startyear, endyear, varname, diagname, format, metric, refinfo):
    """ 
    Writer of averaged data 
    
    Args:
    data: data array
    expname: experiment name
    startyear,endyear: time window
    varname: variable name
    diagname: diagnostics name [series, prof, hovm, map, fld, pdf]
    format: time format [plain, global, monthly, seasonally, yearly]
    metric: tag indicating the type of cost function [base, diff, var, rel, ...]
    
    """

    dirs = config.folders(expname)
    filename = f"{varname}_{expname}_{startyear}-{endyear}_{diagname}_{format}_{metric}"
    if metric != 'base':
        filename += f"_{refinfo['expname']}_{refinfo['startyear']}-{refinfo['endyear']}_{refinfo['diagname']}_{refinfo['format']}"
    filename = os.path.join(dirs['post'], f"{filename}.nc")

    logging.info('File to be loaded %s', filename)
    data.to_netcdf(filename, mode='w', engine='netcdf4', format='NETCDF4')

    return None


# MAIN FUNCTION
def postreader_nemo(expname, startyear, endyear, varname, diagname, format='global', orca='ORCA2', 
                    replace=False, metric='base', refinfo=None):
    """ 
    Postreader_nemo: main function for reading averaged data
    
    Args:
    expname: experiment name
    startyear,endyear: time window
    varname: variable name
    diagname: diagnostics name [series, prof, hovm, map, fld, pdf]
    format: time format [plain, global, monthly, seasonally, yearly]
    orca: ORCA configuration [ORCA2, eORCA1]
    replace: replace existing averaged file [False or True]
    metric: compute distance with respect to a reference field using a cost function
    refinfo = {'expname': '****', 'startyear': ****, 'endyear': ****, 'diagname': '*', 'format': '*'}
    
    """

    dirs = config.folders(expname)
    info = catalogue.observables('nemo')[varname]

    ## try to read averaged data
    try:
        if not replace:
            data = reader_averaged(expname=expname, startyear=startyear, endyear=endyear, varname=varname, 
                                   diagname=diagname, format=format, metric=metric, refinfo=refinfo)
            logging.info('Averaged data found.')
            return data 
        else:
            # When replace is True, skip checking for the file and recreate it
            raise FileNotFoundError  # Trigger the exception deliberately to skip reading of averaged file
    except FileNotFoundError:
        if replace:
            logging.info('Averaged data to be replaced. Creating new file ...')
        else:
            logging.info('Averaged data not found. Creating new file ...')

    ## otherwise read original data and perform averaging
    for year in range(startyear, endyear + 1):
        logging.info(f"Processing year {year}")    
        ds = reader_nemo_field(expname=expname, startyear=year, endyear=year, varname=varname)
        data = averaging(data=ds, varname=varname, diagname=diagname, format=format, orca=orca)
        writer_averaged(data=data, expname=expname, startyear=startyear, endyear=endyear, varname=varname, 
                        diagname=diagname, format=format, metric='base', refinfo=None)

    if metric == 'base':
        return data
    else:
        ## if metric is not 'base', compute cost function
        # read reference data or create averaged field
        try:
            if not replace:
                mds = reader_averaged(expname=refinfo['expname'], startyear=refinfo['startyear'], endyear=refinfo['endyear'], 
                                      varname=varname, diagname=refinfo['diagname'], format=refinfo['format'], metric='base', refinfo=None)
                logging.info('Averaged reference data found.')
            else:
                # When replace is True, skip checking for the file and recreate it
                raise FileNotFoundError  # Trigger the exception deliberately to skip reading of averaged file
        except FileNotFoundError:
            if replace:
                logging.info('Averaged reference data to be replaced. Creating new file ...')
            else:
                logging.info('Averaged reference data not found. Creating new file ...')
            xds = reader_nemo_field(expname=refinfo['expname'], startyear=refinfo['startyear'], endyear=refinfo['endyear'], varname=varname)
            mds = averaging(data=xds, varname=varname, diagname=refinfo['diagname'], format=refinfo['format'], orca=orca)
            writer_averaged(data=mds, expname=refinfo['expname'], startyear=refinfo['startyear'], endyear=refinfo['endyear'], 
                            varname=varname, diagname=refinfo['diagname'], format=refinfo['format'], metric='base', refinfo=None)

        # apply cost function
        if refinfo['diagname'] == 'field':

            # apply cost function first and averaging again afterwards
            data = apply_cost_function(data, mds, metric, format=format, format_ref=refinfo['format'])    
            data = averaging(data=data, varname=varname, diagname=diagname, format=format, orca=orca)

        else:

            # apply cost function to averaged data
            data = apply_cost_function(data, mds, metric, format=format, format_ref=refinfo['format'])               
            data = _update_description(data, refinfo)

        writer_averaged(data=data, expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format, metric=metric, refinfo=refinfo)

    # Now you can read
    data = reader_averaged(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname, format=format, metric=metric, refinfo=refinfo)
    
    return data


def averaging(data, varname, diagname, format, orca):
    """ 
    Averaging: Perform different flavours of averaging 
    
    Args:
    data: data array of a single field
    varname: variable name
    diagname: diagnostics name [scalar, series, prof, hovm, map, fld, pdf]
    format: time format [plain, global, monthly, seasonally, yearly]
    orca: ORCA configuration <ORCA2, eORCA1>
    
    """

    info = catalogue.observables('nemo')[varname]

    # scalar / single-valued
    if diagname == 'scalar' or (diagname == 'timeseries' and format == 'global'):
        
        ds = timemean(data=data, format='global')
        ds = spacemean(data=ds, ndim=info['dim'], orca=orca)
        
        ds = xr.Dataset({
            varname : xr.DataArray(data = ds, dims = [], coords = {},
                            attrs  = {'units' : info['units'], 'long_name' : info['long_name']})},
            attrs = {'description': 'ECE4/NEMO global averaged scalar'})


    # timeseries
    if diagname == 'timeseries' and format != 'global':

        ds = timemean(data=data, format=format)
        ds = spacemean(data=ds, ndim=info['dim'], orca=orca)

        #ds = xr.Dataset({
        #        varname : xr.DataArray(data=ds, dims=[ds.sizes[0]], coords={ds.sizes[0]: ds['time']}, 
        #                                attrs = {'units': info['units'], 'long_name': info['long_name']})}, 
        #        attrs = {'description': 'ECE4/NEMO averaged timeseries'})


    # vertical profile
    if (diagname == 'profile' and info['dim'] == '3D'):
        
        data = timemean(data=data, format='global', use_cftime=True)
        data = spacemean(data=data, ndim='2D', orca=orca)

        #ds = xr.Dataset({
        #    varname : xr.DataArray(data=data, dims=['z'], coords={'z': data['z']}, 
        #                           attrs = {'units' : info['units'], 'long_name' : info['long_name']})}, 
        #    attrs = {'description': 'ECE4/NEMO averaged profile'})


    # hovmoller diagram
    if (diagname == 'hovmoller' and info['dim'] == '3D'):

        if (format == 'plain' or format == 'yearly'):

            ds = timemean(data=data, format=format)
            ds = spacemean(data=ds, ndim='2D', orca=orca)

            ds = xr.Dataset({
                    varname : xr.DataArray(data=ds, dims=['time', 'z'], coords={'time': ds['time'], 'z': ds['z']}, 
                                            attrs = {'units': info['units'], 'long_name': info['long_name']})}, 
                    attrs = {'description': 'ECE4/NEMO averaged Hovmoller diagram'})


    # 2D horizontal map 
    # ISSUE: what if format != 'global'?
    if diagname == 'map':

        ds = timemean(data=data, format='global')
        if info['dim'] == '3D':
            ds  = spacemean(data=ds, ndim='1D', orca=orca)      

        #ds = xr.Dataset({
        #    'lat': xr.DataArray(data = data['lat'], dims = ['y', 'x'], coords = {'y': data['y'], 'x': data['x']}, 
        #                attrs = {'units' : 'deg', 'long_name' : 'latitude'}),
        #    'lon': xr.DataArray(data = data['lon'], dims = ['y', 'x'], coords = {'y': data['y'], 'x': data['x']}, 
        #                attrs = {'units' : 'deg', 'long_name' : 'longitude'}),                   
        #    varname : xr.DataArray(data = ds, dims = ['y', 'x'], coords = {'y': data['y'], 'x': data['x']},
        #                attrs  = {'units' : info['units'], 'long_name' : info['long_name']})}, 
        #    attrs = {'description': 'ECE4/NEMO averaged map'})


    # time-averaged spatial-only field 
    if diagname == 'field':

        vec = timemean(data=data, format=format)

        data_vars = {
            'lat': xr.DataArray(data=data['lat'], dims=['y', 'x'], coords={'y': data['y'], 'x': data['x']}, 
                        attrs={'units': 'deg', 'long_name': 'latitude'}),
            'lon': xr.DataArray(data=data['lon'], dims=['y', 'x'], coords={'y': data['y'], 'x': data['x']}, 
                        attrs={'units': 'deg', 'long_name': 'longitude'})}

        if info['dim'] == '3D':
            data_vars['z'] = xr.DataArray(data=data['z'], dims=['z'], coords={'z': data['z']}, 
                        attrs={'units': 'm', 'long_name': 'depth'})
            data_vars[varname] = xr.DataArray(data=vec, dims=['z', 'y', 'x'], coords={'z': data['z'], 'y': data['y'], 'x': data['x']},
                        attrs={'units': info['units'], 'long_name': info['long_name']})
        elif info['dim'] == '2D': 
            data_vars[varname] = xr.DataArray(data=vec, dims=['y', 'x'], coords={'y': data['y'], 'x': data['x']},
                        attrs={'units': info['units'], 'long_name': info['long_name']})

        # Create the dataset
        ds = xr.Dataset(data_vars=data_vars, attrs={'description': 'ECE4/NEMO Time-averaged field'})

    return ds


##########################################################################################
##########################################################################################

