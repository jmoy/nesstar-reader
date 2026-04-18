# nesstar-reader

`nesstar-reader` is an open-source extractor for `.Nesstar` survey data containers. It reverse-engineers the binary NESSTAR/NSDstat format well enough to export the tested MoSPI datasets into delimited data files plus per-dataset JSON metadata, and the repository includes notes documenting the recovered format in [`nesstar_format.md`](nesstar_format.md).

## CLI

Install the package and run the `nesstar-reader` command:

```bash
pip install .
nesstar-reader INPUT.Nesstar --output-dir out
```

The CLI takes one positional argument:

- `nesstar`: path to the input `.Nesstar` file

You must provide exactly one output target:

- `--output-prefix PREFIX`: write files as `PREFIX_datasetNN_<name>.<ext>`
- `--output-dir DIR`: write files into `DIR` using the input filename stem as the prefix

Optional flags:

- `--tsv`: write tab-separated data files instead of CSV
- `--no-header`: omit the header row from extracted data files
- `--compressed`: gzip-compress the extracted data files
- `--category-labels`: replace numeric categorical codes with labels from embedded category metadata when available

For each dataset in the container, the CLI writes one data file and one JSON
metadata file, then prints their paths to stdout.
