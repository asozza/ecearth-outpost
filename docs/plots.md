# Plots

Command line tools that plot the [aggregated data](aggregated-data.md). Missing
aggregated files are produced on the fly, as in `climatology`. Figures are written
in the `post` folder of the **first** experiment.

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
| `-e`         | `EXPNAME STARTYEAR ENDYEAR`, repeat for each experiment              |
| `-v`         | variables, as named in [catalogue](../src/ecpost/utils/catalogue.py) |
| `--mode`     | `plain` (monthly, default), `yearly`, `monthly`/`seasonally` (seasonal cycle) |
| `--moving`   | 12-month moving average (`--mode plain` only)                        |
| `--rescale`  | divide each series by its initial value                              |
| `--timeoff`  | offset added to the time axis                                        |
| `--labels`   | legend labels, one per experiment (default: experiment names)        |
| `--config`   | configuration file (default `./config.yml`)                          |
| `--orca`     | grid, `ORCA2` (default) or `eORCA1`                                  |
| `--metric`   | `base` (default), `diff`, `norm`, … ; requires `--ref`               |
| `--ref`      | `REFEXP REFSTART REFEND`, reference for `--metric`                   |
| `--replace`  | recompute existing aggregated files                                  |
| `--format`   | figure format, `png` (default), `pdf`, …                             |
| `--dpi`      | figure resolution (default 150)                                      |

Figures are named `EXP1[-EXP2...]_Y1-Y2_VAR_timeseries[_MODE][_movave][_METRIC].FMT`,
where `Y1-Y2` spans all the experiment windows.

Without installing the package: `PYTHONPATH=src python -m ecpost.launch.launch_timeseries ...`
