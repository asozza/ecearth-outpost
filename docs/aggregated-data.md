# Aggregated data

The NEMO output is reduced to light-weight files stored in the experiment `post` folder.
The core is [`ecpost.io.postreader`](../src/ecpost/io/postreader.py); the
`climatology` command is a thin wrapper around it.

## Diagnostics

Only four diagnostics are computed from the raw output:

| Diagnostic   | Variables | Space mean          | Time mean          | Output dims   |
|--------------|-----------|---------------------|--------------------|---------------|
| `timeseries` | 2D, 3D    | surface / volume    | none (monthly)     | `time`        |
| `hovmoller`  | 3D        | horizontal          | none (monthly)     | `time, z`     |
| `map`        | 2D, 3D    | vertical (3D only)  | over the window    | `y, x`        |
| `field`      | 2D, 3D    | none                | over the window    | `[z,] y, x`   |

Everything else is a time mean of `timeseries` or `hovmoller`, computed on the fly
when reading (see [Derived products](#derived-products)): yearly series, seasonal
cycles, vertical profiles, single values. Space and time means commute because the
grid weights (`domain_cfg.nc`) do not change in time; land points (NaN) are ignored.

## Command line

```bash
climatology EXPNAME STARTYEAR ENDYEAR -v VAR [VAR ...] [-d DIAG ...] [options]
```

```bash
# all diagnostics
climatology cs00 1990 1999 -v thetao tos --config config.yml

# only some diagnostics
climatology cs00 1990 1999 -v thetao -d timeseries hovmoller

# difference with respect to the climatology of a reference experiment
climatology cs01 1990 1999 -v thetao -d hovmoller --metric diff --ref cs00 1990 1999
```

| Option       | Meaning                                                        |
|--------------|----------------------------------------------------------------|
| `-v`         | variables, as named in [catalogue](../src/ecpost/utils/catalogue.py) |
| `-d`         | diagnostics (default: all); not applicable ones are skipped    |
| `--config`   | configuration file (default: `config.yml` in the current directory, then in the repository root)                    |
| `--orca`     | grid, `ORCA2` (default) or `eORCA1`                            |
| `--metric`   | `base` (default), `diff`, `norm`, … ; requires `--ref`         |
| `--ref`      | `REFEXP REFSTART REFEND`, reference for `--metric`             |
| `--replace`  | recompute existing files                                       |
| `--cleanup`  | remove single-year and redundant merged files after merging    |
| `--quiet`    | do not print the aggregated data                               |

Without installing the package: `PYTHONPATH=src python -m ecpost.launch.launch_climatology ...`

## How it works

Files are named `EXP_Y1-Y2_VAR_DIAG[_METRIC].nc`.

1. If the file for the requested window already exists it is read and nothing else
   is done (unless `--replace`).
2. Existing multi-year files lying **inside** `[Y1, Y2]` are reused; the remaining
   years are computed one by one. Raw data of each year are read **once** for all
   diagnostics and written as single-year files `EXP_Y-Y_VAR_DIAG.nc`.
3. Single-year files and reused blocks are merged into `EXP_Y1-Y2_VAR_DIAG.nc`:
   `timeseries` and `hovmoller` are concatenated in time, `map` and `field` are
   averaged weighting each file by its number of years.

Extending a window (e.g. 1990-1999 → 1990-2009) therefore only processes the new years.
With a metric other than `base`, the metric is applied to the raw data before any
average, so derived products remain consistent also for non-linear metrics.

## Python API

```python
from ecpost.io.postreader import postreader_nemo, postreader_nemo_multi

# one diagnostic
ds = postreader_nemo("cs00", 1990, 1999, "thetao", "hovmoller", config_path="config.yml")

# several diagnostics, raw data read once per year
res = postreader_nemo_multi("cs00", 1990, 1999, "thetao", ["timeseries", "map"], config_path="config.yml")
res["map"]
```

### Derived products

Time means of the stored diagnostics; extra keyword arguments are passed to
`postreader_nemo` (`metric`, `refinfo`, `orca`, `replace`, `config_path`, …).

| Function                                  | From         | `mode`                                        |
|-------------------------------------------|--------------|-----------------------------------------------|
| `get_timeseries(exp, y1, y2, var, mode)`  | `timeseries` | `plain` (default), `yearly`, `monthly`, `seasonally`, `global` |
| `get_hovmoller(exp, y1, y2, var, mode)`   | `hovmoller`  | `plain` (default), `yearly`                   |
| `get_profile(exp, y1, y2, var, mode)`     | `hovmoller`  | `global` (default), `monthly`, `seasonally`   |
| `get_climatology(exp, y1, y2, var)`       | `field`      | —                                             |

`monthly` / `seasonally` give the climatological cycle (`month` / `season` dims),
`yearly` the annual means (`year` dim), `global` the mean over the whole window.

```python
from ecpost.io.postreader import get_timeseries, get_profile

annual = get_timeseries("cs00", 1990, 1999, "thetao", mode="yearly", config_path="config.yml")
prof = get_profile("cs00", 1990, 1999, "thetao", mode="seasonally", config_path="config.yml")
```
