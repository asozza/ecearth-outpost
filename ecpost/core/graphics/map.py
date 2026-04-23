import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cmocean
import numpy as np

def plot_nemo_map(data, lon, lat, ax=None, mask=None, 
                  projection=ccrs.Robinson(),
                  title="NEMO Field", 
                  cbar_label="",
                  cmap=cmocean.cm.balance,
                  **kwargs):
    """
    Funzione modulare per plottare mappe NEMO con Cartopy.
    
    data: xarray DataArray o numpy array
    lon, lat: coordinate ORCA
    ax: axes esistente (opzionale)
    mask: array booleano o masked_array per i continenti
    **kwargs: passati direttamente a pcolormesh (es. vmin, vmax)
    """
    if ax is None:
        fig = plt.figure(figsize=(12, 6))
        ax = plt.axes(projection=projection)
    
    # Impostazioni base Cartopy
    ax.set_global()
    ax.coastlines(resolution='110m', color='black', linewidth=0.5)
    ax.gridlines(draw_labels=True, linestyle='--', alpha=0.5)

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

    plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02, shrink=0.8, label=cbar_label)
    ax.set_title(title, fontsize=14)
    
    return ax