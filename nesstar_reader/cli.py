"""Command-line entry point for NESSTAR extraction."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .exporter import export_nesstar_to_csv_and_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nesstar-reader",
        description="Extract datasets from a .Nesstar container into CSV plus JSON metadata.",
    )
    parser.add_argument("nesstar", help="Path to the input .Nesstar file.")
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument(
        "--output-prefix",
        help="Output file prefix. Each dataset will be written as <prefix>_datasetNN_<name>.csv/.json.",
    )
    output_group.add_argument(
        "--output-dir",
        help="Output directory. Files will be created inside it using the input stem as prefix.",
    )
    parser.add_argument(
        "--tsv",
        action="store_true",
        help="Write tab-separated output (.tsv) instead of CSV.",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Do not write a header row in the extracted data files.",
    )
    parser.add_argument(
        "--compressed",
        action="store_true",
        help="Compress extracted data files as .gz output.",
    )
    parser.add_argument(
        "--category-labels",
        action="store_true",
        help="Replace numeric categorical codes with labels from embedded Categories metadata when available.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    written = export_nesstar_to_csv_and_json(
        Path(args.nesstar),
        output_prefix=args.output_prefix,
        output_dir=args.output_dir,
        delimiter="\t" if args.tsv else ",",
        include_header=not args.no_header,
        compressed=args.compressed,
        use_category_labels=args.category_labels,
    )

    for item in written:
        print(f"dataset {item['dataset_number']}:")
        print(f"  data: {item['data']}")
        print(f"  json: {item['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
