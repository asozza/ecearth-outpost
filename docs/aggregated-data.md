# Aggregated data

The NEMO output is reduced to light-weight files (timeseries, profiles, hovmoller
diagrams, maps, time-averaged fields) stored in the experiment `post` folder.
The core is [`ecpost.io.postreader`](../src/ecpost/io/postreader.py); the
`climatology` command is a thin wrapper around it.

## Command line

```bash
climatology EXPNAME STARTYEAR ENDYEAR -v VAR [VAR ...] [-d DIAG[:MODE] ...] [options]
```

```bash
# default diagnostics (timeseries, profile, hovmoller, map, field)
climatology cs00 1990 1999 -v thetao tos --config config.yml

# choose diagnostics and time modes
climatology cs00 1990 1999 -v thetao -d timeseries:yearly profile map:seasonally

# difference with respect to the climatology of a reference experiment
climatology cs01 1990 1999 -v thetao -d profile --metric diff --ref cs00 1990 1999
```

| Option       | Meaning                                                        |
|--------------|----------------------------------------------------------------|
| `-v`         | variables, as named in [catalogue](../src/ecpost/utils/catalogue.py) |
| `-d`         | diagnostics, optionally `diag:mode` (default mode: first in table below) |
| `--config`   | configuration file (default `./config.yml`)                    |
| `--orca`     | grid, `ORCA2` (default) or `eORCA1`                            |
| `--metric`   | `base` (default), `diff`, `norm`, … ; requires `--ref`         |
| `--ref`      | `REFEXP REFSTART REFEND`, reference for `--metric`             |
| `--replace`  | recompute existing files                                       |
| `--cleanup`  | remove single-year and redundant merged files after merging    |
| `--quiet`    | do not print the aggregated data                               |

Without installing the package: `PYTHONPATH=src python -m ecpost.launch.launch_climatology ...`

## Diagnostics

| Diagnostic   | Variables | Modes                                          | Output dims                  |
|--------------|-----------|------------------------------------------------|------------------------------|
| `timeseries` | 2D, 3D    | plain, yearly, monthly, seasonally, global     | time axis only               |
| `profile`    | 3D        | global, monthly, seasonally                    | `z`                          |
| `hovmoller`  | 3D        | plain, yearly                                  | time axis × `z`              |
| `map`        | 2D, 3D    | global, monthly, seasonally                    | `y, x` (3D: vertical mean)   |
| `field`      | 2D, 3D    | global, monthly, seasonally                    | `[z,] y, x`                  |
| `scalar`     | 2D, 3D    | global                                         | none                         |

Time modes:

- `plain`: monthly values as in the output (`time`)
- `yearly`: annual means (`year`)
- `monthly` / `seasonally`: climatological cycle (`month` / `season`)
- `global`: mean over the whole window

Spatial means are weighted with the cell metrics of `domain_cfg.nc`
(volume, area or layer thickness); land points (NaN) are ignored.

## How it works

1. For each requested diagnostic, if `EXP_Y1-Y2_VAR_DIAG_MODE.nc` already exists it is
   read and nothing else is done (unless `--replace`).
2. Existing multi-year files lying **inside** `[Y1, Y2]` are reused; the remaining
   years are computed one by one. Raw data of each year are read **once** for all
   diagnostics and written as single-year files `EXP_Y-Y_VAR_DIAG_MODE.nc`.
3. Single-year files and reused blocks are merged into `EXP_Y1-Y2_VAR_DIAG_MODE.nc`:
   - data with a `time` or `year` axis are concatenated;
   - all the others (climatologies) are averaged, weighting each file by its number of years.

Extending a window (e.g. 1990-1999 → 1990-2009) therefore only processes the new years.
With a metric other than `base`, the suffix `_METRIC` is appended to the file names.

## Python API

```python
from ecpost.io.postreader import postreader_nemo, postreader_nemo_multi, get_climatology

# one diagnostic
ds = postreader_nemo("cs00", 1990, 1999, "thetao", "profile", mode="global", config_path="config.yml")

# several diagnostics, raw data read once per year
res = postreader_nemo_multi("cs00", 1990, 1999, "thetao",
                            diagnostics=[("timeseries", "yearly"), ("map", "global")],
                            config_path="config.yml")
res[("map", "global")]

# time-averaged field (same as diagnostic 'field', mode 'global')
clim = get_climatology("cs00", 1990, 1999, "thetao", config_path="config.yml")
```
