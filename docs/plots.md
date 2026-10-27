# Plots

Command line tools that plot the [aggregated data](aggregated-data.md). Missing
aggregated files are produced on the fly, as in `climatology`.

All tools accept one or more experiments (`-e EXPNAME STARTYEAR ENDYEAR`, repeated),
drawn in the same figure. The **first** experiment defines the workspace: figures
are written in its `post` folder. They are named
`EXP1[-EXP2...]_Y1-Y2_VAR_PLOT[_OPTIONS][_METRIC].FMT`, where `Y1-Y2` spans all the
experiment windows.

Options shared by all tools:

| Option       | Meaning                                                              |
|--------------|----------------------------------------------------------------------|
| `-e`         | `EXPNAME STARTYEAR ENDYEAR`, repeat for each experiment              |
| `-v`         | variables, as named in [catalogue](../src/ecpost/utils/catalogue.py) |
| `--labels`   | legend labels, one per experiment (default: experiment names)        |
| `--config`   | configuration file (default `./config.yml`)                          |
| `--orca`     | grid, `ORCA2` (default) or `eORCA1`                                  |
| `--metric`   | `base` (default), `diff`, `norm`, … ; requires `--ref`               |
| `--ref`      | `REFEXP REFSTART REFEND`, reference for `--metric`                   |
| `--replace`  | recompute existing aggregated files                                  |
| `--format`   | figure format, `png` (default), `pdf`, …                             |
| `--dpi`      | figure resolution (default 150)                                      |

Without installing the package: `PYTHONPATH=src python -m ecpost.launch.launch_<tool> ...`

## timeseries

Surface/volume mean of one or more variables, one figure per variable, with any
number of experiments in the same plot.

```bash
timeseries -e EXPNAME STARTYEAR ENDYEAR [-e ...] -v VAR [VAR ...] [options]
```

```bash
# one experiment
timeseries -e cs00 1990 1999 -v thetao tos --config config.yml

# two experiments (different windows are allowed), annual means, custom labels
timeseries -e cs00 1990 1999 -e cs01 1990 2009 -v thetao --mode yearly --labels control warming

# seasonal cycle
timeseries -e cs00 1990 1999 -e cs01 1990 1999 -v tos --mode seasonally

# difference with respect to the climatology of a reference experiment
timeseries -e cs01 1990 1999 -v thetao --metric diff --ref cs00 1990 1999
```

| Option       | Meaning                                                              |
|--------------|----------------------------------------------------------------------|
| `--mode`     | `plain` (monthly, default), `yearly`, `monthly`/`seasonally` (seasonal cycle) |
| `--moving`   | 12-month moving average (`--mode plain` only)                        |
| `--rescale`  | divide each series by its initial value                              |
| `--timeoff`  | offset added to the time axis                                        |

Figure name: `EXP1[-EXP2...]_Y1-Y2_VAR_timeseries[_MODE][_movave][_METRIC].FMT`.

## profile

Vertical profiles (horizontal mean) of 3D variables, from the `hovmoller` diagnostic,
one figure per variable, with any number of experiments in the same plot.

```bash
profile -e EXPNAME STARTYEAR ENDYEAR [-e ...] -v VAR [VAR ...] [options]
```

```bash
# mean over the window, two experiments, upper 1000 m
profile -e cs00 1990 1999 -e cs01 1990 2009 -v thetao so --zmax 1000

# one panel per season
profile -e cs00 1990 1999 -e cs01 1990 1999 -v thetao --mode seasonally

# difference with respect to the climatology of a reference experiment
profile -e cs01 1990 1999 -v thetao --metric diff --ref cs00 1990 1999
```

| Option       | Meaning                                                              |
|--------------|----------------------------------------------------------------------|
| `--mode`     | `global` (mean over the window, default), `seasonally` (4 panels), `monthly` (12 panels) |
| `--zmax`     | maximum depth shown [m]; the x axis is rescaled on the visible part   |

2D variables are skipped. Figure name: `EXP1[-EXP2...]_Y1-Y2_VAR_profile[_MODE][_METRIC].FMT`.
