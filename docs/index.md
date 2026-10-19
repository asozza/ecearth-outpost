# ecearth-outpost documentation

- [Configuration](configuration.md): folder layout and `config.yml`
- [Aggregated data](aggregated-data.md): the `climatology` pipeline and the `postreader` API

## Package layout

```
src/ecpost/
├── io/        readers of NEMO output and domain, postreader (aggregated data)
├── means/     time/space averaging, metrics, regridding
├── utils/     configuration, variable catalogue, time tools
├── graphics/  plotting functions (built on top of postreader)
└── launch/    command line tools
```
