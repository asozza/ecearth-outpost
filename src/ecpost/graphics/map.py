#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Graphics for horizontal maps

Author: Alessandro Sozza (CNR-ISAC)
Date: Oct 2026
"""

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cmocean
import numpy as np

from ecpost.utils import catalogue
from ecpost.io.postreader import postreader_nemo


def read_map(expname, startyear, endyear, varname, depth=None, orca="ORCA2", replace=False,
             metric="base", refinfo=None, config_path=None):
    """
    Horizontal map averaged over the time window, from the aggregated data

    - depth None: 'map' diagnostic (vertical mean for 3D variables, the field itself for 2D ones)
    - depth [m]: 'field' diagnostic at the nearest model level (3D variables only)

    Returns the DataArray, with 2D 'lon' and 'lat' coordinates
    """

    ndim = catalogue.observables('nemo')[varname]['dim']
    if depth is not None and ndim != '3D':
        raise ValueError(f"depth requires a 3D variable, '{varname}' is {ndim}")

    diagname = 'map' if depth is None else 'field'
    data = postreader_nemo(expname=expname, startyear=startyear, endyear=endyear, varname=varname, diagname=diagname,
                           metric=metric, refinfo=refinfo, orca=orca, replace=replace, config_path=config_path)
    data = data[varname]
    if depth is not None:
        data = data.sel(z=depth, method='nearest')
    data = data.squeeze(drop=True)

    if 'lon' not in data.coords or 'lat' not in data.coords:
        raise ValueError(f"No lon/lat coordinates in the '{diagname}' data of {expname}")

    return data

def plot_map(data, lon, lat, ax=None, mask=None, 
                  projection=ccrs.Robinson(),
                  title="NEMO Field", 
                  cbar_label="",
                  cmap=cmocean.cm.balance,
                  colorbar=True,
                  **kwargs):
    """
    Funzione modulare per plottare mappe NEMO con Cartopy.
    
    data: xarray DataArray o numpy array
    lon, lat: coordinate ORCA
    ax: axes esistente (opzionale)
    mask: array booleano o masked_array per i continenti
    colorbar: aggiunge la colorbar al pannello (False per una colorbar comune a più pannelli)
    **kwargs: passati direttamente a pcolormesh (es. vmin, vmax)
    """
    if ax is None:
        fig = plt.figure(figsize=(12, 6))
        ax = plt.axes(projection=projection)
    
    # Impostazioni base Cartopy
    ax.set_global()
    ax.coastlines(resolution='110m', color='black', linewidth=0.5)
    gl = ax.gridlines(draw_labels=True, linestyle='--', alpha=0.5)
    gl.top_labels = False
    gl.right_labels = False

    # Plot del campo
    # Usiamo pcolormesh che gestisce bene le griglie curvilinee di NEMO
    im = ax.pcolormesh(
        lon, lat, data,
        transform=ccrs.PlateCarree(),
        cmap=cmap,
        shading='auto',
        **kwargs
    )
    
    # Overlay della maschera se fornita
    if mask is not None:
        # Assumiamo che la maschera abbia 1 su terra e 0 su mare o NaN
        # Usiamo una colormap 'grigia' per la terra
        ax.pcolormesh(
            lon, lat, mask,
            transform=ccrs.PlateCarree(),
            cmap='binary', # o una ListedColormap custom
            vmin=0, vmax=1,
            zorder=2
        )

    if colorbar:
        plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02, shrink=0.8, label=cbar_label)
    ax.set_title(title, fontsize=14)
    
    return ax