# Configuration

Paths are read from a `config.yml` file. By default it is looked up in the current
directory; a different file can be given with `--config` (command line) or
`config_path=` (Python API).

```yaml
base_path: /path/to/experiments   # one sub-folder per experiment
src_path:  /path/to/sources       # contains rebuild_nemo
data_path: /path/to/data          # contains nemo/domain/<ORCA>/domain_cfg.nc
```

Paths can also be grouped by platform (`sys.platform`), so that the same file works
on several machines, see [config-example.yml](../config-example.yml):

```yaml
darwin:
  base_path: ...
linux:
  base_path: ...
```

## Folder layout

For an experiment `EXP`:

| Folder                                  | Content                                      |
|-----------------------------------------|----------------------------------------------|
| `base_path/EXP/output/nemo`             | NEMO output, `EXP_oce_1m_T_YYYY-YYYY.nc`, …  |
| `base_path/EXP/post`                    | aggregated data (created if missing)         |
| `data_path/nemo/domain/ORCA2/domain_cfg.nc` | grid metrics used for spatial averages   |
