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
| `--config`   | configuration file (default: `config.yml` in the current directory, then in the repository root)                          |
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

## layers

Timeseries of 3D variables averaged over depth layers, one panel per layer, with any
number of experiments in the same panels. Data come from the `hovmoller` diagnostic:
each model level is assigned to a layer by the depth of its T-point and weighted by its
wet volume. The `total` panel is the volume mean of the full column (equal to the
`timeseries` diagnostic up to partial-cell effects, ~1e-3 °C for `thetao` in ORCA2).

```bash
layers -e EXPNAME STARTYEAR ENDYEAR [-e ...] -v VAR [VAR ...] [options]
```

```bash
# default layers: 0-100, 100-300, 300-700, 700-2000, 2000-bottom m and total (6 panels)
layers -e cs00 1990 1999 -e cs01 1990 2009 -v thetao so

# custom interfaces: 0-700, 700-2000, 2000-bottom m and total (4 panels), annual means
layers -e cs00 1990 1999 -v thetao --layers 0 700 2000 --mode yearly
```

| Option       | Meaning                                                              |
|--------------|----------------------------------------------------------------------|
| `--layers`   | layer interfaces [m]; the last layer goes down to the bottom and the full column is always added (default `0 100 300 700 2000`) |
| `--mode`     | `plain` (monthly, default), `yearly`, `monthly`/`seasonally` (seasonal cycle) |
| `--moving`   | 12-month moving average (`--mode plain` only)                        |
| `--rescale`  | divide each series by its initial value                              |
| `--timeoff`  | offset added to the time axis                                        |

2D variables are skipped. Figure name: `EXP1[-EXP2...]_Y1-Y2_VAR_layers[_MODE][_movave][_METRIC].FMT`.

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

## hovmoller

Horizontal mean of 3D variables as function of time and depth, from the `hovmoller`
diagnostic. One panel per experiment, stacked, with a common time axis and a common
color scale.

```bash
hovmoller -e EXPNAME STARTYEAR ENDYEAR [-e ...] -v VAR [VAR ...] [options]
```

```bash
# two experiments, upper 1000 m
hovmoller -e cs00 1990 1999 -e cs01 1990 2009 -v thetao --zmax 1000

# annual means, difference with respect to a reference climatology
hovmoller -e cs01 1990 1999 -v thetao --mode yearly --metric diff --ref cs00 1990 1999
```

| Option         | Meaning                                                         |
|----------------|-----------------------------------------------------------------|
| `--mode`       | `plain` (monthly, default) or `yearly`                          |
| `--zmax`       | maximum depth shown [m] (default 5000)                          |
| `--rescale`    | divide each level by its initial value                          |
| `--timeoff`    | offset added to the time axis                                   |
| `--vmin/--vmax`| color scale limits (default: 2nd-98th percentiles of all panels, symmetric around 0 with `--metric`) |
| `--cmap`       | colormap (default `RdYlBu_r`, `cmo.balance` with `--metric`)    |

2D variables are skipped. Figure name: `EXP1[-EXP2...]_Y1-Y2_VAR_hovmoller[_MODE][_METRIC].FMT`.

## map

Horizontal maps averaged over the time window, one panel per experiment (two columns)
with a common color scale. By default the `map` diagnostic is used: vertical mean for
3D variables, the field itself for 2D ones. With `--depth` the model level nearest to
the given depth is taken from the `field` diagnostic (heavier, 3D variables only).

```bash
map -e EXPNAME STARTYEAR ENDYEAR [-e ...] -v VAR [VAR ...] [options]
```

```bash
# sea surface temperature of three experiments
map -e cs00 1990 1999 -e cs01 1990 2009 -e cs02 1990 1999 -v tos

# temperature at 100 m
map -e cs00 1990 1999 -e cs01 1990 1999 -v thetao --depth 100

# difference with respect to a reference climatology
map -e cs01 1990 1999 -v tos --metric diff --ref cs00 1990 1999
```

| Option         | Meaning                                                         |
|----------------|-----------------------------------------------------------------|
| `--depth`      | depth [m] of the level to plot (default: vertical mean)         |
| `--projection` | `robinson` (default), `platecarree`, `mollweide`                |
| `--vmin/--vmax`| color scale limits (default: 2nd-98th percentiles of all panels, symmetric around 0 with `--metric`) |
| `--cmap`       | colormap (default `RdYlBu_r`, `cmo.balance` with `--metric`)    |

Figure name: `EXP1[-EXP2...]_Y1-Y2_VAR_map[_zDEPTH][_METRIC].FMT`.
