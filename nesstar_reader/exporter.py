"""Streaming dataset exporter for NESSTAR containers."""

from __future__ import annotations

from collections.abc import Callable
import csv
import gzip
import json
from pathlib import Path
import re
import struct
from typing import Any

from .binary import parse_embedded_dataset_metadata, parse_nesstar_binary


RowValue = bytes | int | float | None
ChunkReader = Callable[[int, int], list[RowValue]]
DEFAULT_CHUNK_SIZE = 10_000


def _sanitize_filename_part(value: str) -> str:
    """Return a conservative fallback filename component."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "dataset"


def _decode_nul_terminated_byte_string(raw: bytes) -> bytes:
    """Trim a fixed-width mode-1 byte-string cell at its first NUL byte."""
    # Mode 1 stores byte strings in fixed-size slots and terminates them with NUL.
    return raw.split(b"\x00", 1)[0]


def _format_output_value(value: RowValue) -> bytes:
    """Format one row value for the binary TSV writer path."""
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, float) and value.is_integer():
        return str(int(value)).encode("ascii")
    return str(value).encode("ascii")


def _format_output_text(value: RowValue) -> str:
    """Format one row value for the text-mode CSV writer path."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="surrogateescape")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _normalize_category_value(value: object) -> object:
    """Normalize category ids so XML labels match decoded numeric values."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return stripped
        try:
            return int(stripped)
        except ValueError:
            try:
                parsed = float(stripped)
            except ValueError:
                return stripped
            return int(parsed) if parsed.is_integer() else parsed
    return value


def _build_category_label_map(categories: list[object]) -> dict[object, bytes]:
    """Build a normalized code-to-label map for optional label substitution."""
    mapping: dict[object, bytes] = {}
    for category in categories:
        key = _normalize_category_value(category.value)
        mapping[key] = category.label.encode("utf-8")
    return mapping


def _build_nul_terminated_byte_string_chunk_reader(
    data: bytes,
    start: int,
    width: int,
) -> ChunkReader:
    """Create a reader for fixed-width NUL-terminated string cells."""
    def reader(row_start: int, row_count: int) -> list[RowValue]:
        """Read a contiguous row window for one mode-1 variable."""
        values: list[RowValue] = []
        offset = start + row_start * width
        end = offset + row_count * width
        for cell_start in range(offset, end, width):
            values.append(_decode_nul_terminated_byte_string(data[cell_start : cell_start + width]))
        return values

    return reader


def _build_compact_chunk_reader(
    data: bytes,
    start: int,
    variable: Any,
    *,
    category_label_map: dict[object, bytes] | None = None,
) -> ChunkReader:
    """Create a streaming reader for one compact binary numeric variable.

    The returned callable decodes only the requested row window. It applies the
    same missing-value sentinel and additive-offset semantics as the eager
    compact decoder, and may replace decoded category codes with UTF-8 labels
    when the caller supplies a category map.
    """
    family = variable.value_family
    additive_offset = variable.additive_offset
    missing_value_code = variable.missing_value_code

    def apply(value: int | float) -> RowValue:
        """Apply missing-sentinel and additive-offset semantics to one value."""
        if missing_value_code is not None and value == missing_value_code:
            return None
        if additive_offset is not None:
            return value + additive_offset
        return value

    def maybe_replace_label(value: RowValue) -> RowValue:
        """Replace a decoded category code with its label when configured."""
        if value is None or category_label_map is None:
            return value
        return category_label_map.get(_normalize_category_value(value), value)

    if family == "nibble-packed":
        def reader(row_start: int, row_count: int) -> list[RowValue]:
            """Read a nibble-packed row window using high nibble for even rows."""
            values: list[RowValue] = []
            row_end = row_start + row_count
            for row_index in range(row_start, row_end):
                byte = data[start + row_index // 2]
                value = (byte >> 4) & 0x0F if row_index % 2 == 0 else byte & 0x0F
                values.append(maybe_replace_label(apply(value)))
            return values

        return reader

    if family == "byte-coded":
        def reader(row_start: int, row_count: int) -> list[RowValue]:
            """Read a one-byte-per-row compact numeric window."""
            chunk = data[start + row_start : start + row_start + row_count]
            return [maybe_replace_label(apply(value)) for value in chunk]

        return reader

    if family == "uint16":
        step = 2
    elif family == "uint24":
        step = 3
    elif family == "uint32":
        step = 4
    elif family == "uint40":
        step = 5
    else:
        step = 0

    if step:
        def reader(row_start: int, row_count: int) -> list[RowValue]:
            """Read a fixed-width little-endian integer compact window."""
            values: list[RowValue] = []
            offset = start + row_start * step
            end = offset + row_count * step
            for cell_start in range(offset, end, step):
                values.append(maybe_replace_label(apply(int.from_bytes(data[cell_start : cell_start + step], "little"))))
            return values

        return reader

    if family == "float64":
        def reader(row_start: int, row_count: int) -> list[RowValue]:
            """Read a little-endian float64 compact numeric window."""
            values: list[RowValue] = []
            offset = start + row_start * 8
            end = offset + row_count * 8
            for cell_start in range(offset, end, 8):
                values.append(maybe_replace_label(apply(struct.unpack("<d", data[cell_start : cell_start + 8])[0])))
            return values

        return reader

    raise ValueError(f"Unsupported compact family {family!r} for variable {variable.name}")


def _dataset_output_stem(base: Path, dataset_number: int, file_name: str) -> Path:
    """Choose the output stem for one dataset while stripping path components."""
    safe_name = re.split(r"[\\/]+", file_name.strip())[-1] if file_name else ""
    if safe_name not in {"", ".", ".."}:
        return base.parent / safe_name
    return base.parent / f"{base.name}_dataset{dataset_number:02d}_{_sanitize_filename_part(file_name)}"


def _append_suffix(path: Path, suffix: str) -> Path:
    """Append a suffix without treating dots in the stem as file extensions."""
    return path.parent / f"{path.name}{suffix}"


def _ordered_variable_names(dataset: Any, embedded_dataset: Any | None) -> list[str]:
    """Return export variable order, preferring embedded metadata order."""
    declared_names = [
        variable.variable_name
        for variable in (embedded_dataset.variables if embedded_dataset is not None else [])
    ]
    available_names = {variable.name for variable in dataset.variables}
    ordered = [name for name in declared_names if name in available_names]
    seen = set(ordered)
    ordered.extend(variable.name for variable in dataset.variables if variable.name not in seen)
    return ordered


def _build_dataset_metadata_json(
    dataset: Any,
    embedded_dataset: Any | None,
    nesstar_path: Path,
) -> dict[str, Any]:
    """Build the JSON-serializable metadata sidecar for one exported dataset."""
    embedded_vars = {
        var.variable_name: var
        for var in (embedded_dataset.variables if embedded_dataset is not None else [])
    }
    ordered_names = _ordered_variable_names(dataset, embedded_dataset)
    dataset_vars = {
        variable.name: variable
        for variable in dataset.variables
    }

    variables_json: list[dict[str, Any]] = []
    for variable_name in ordered_names:
        variable = dataset_vars[variable_name]
        embedded_var = embedded_vars.get(variable.name)
        variables_json.append({
            "name": variable.name,
            "variable_id": variable.variable_id,
            "width_value": variable.width_value,
            "mode_code": variable.mode_code,
            "value_format_code": variable.value_format_code,
            "value_offset_i64": variable.value_offset_i64,
            "value_family": variable.value_family,
            "embedded": (
                {
                    "label": embedded_var.label,
                    "label_resource_id": embedded_var.label_resource_id,
                    "category_resource_id": embedded_var.category_resource_id,
                    "categories": [
                        {"value": category.value, "label": category.label}
                        for category in embedded_var.categories
                    ],
                }
                if embedded_var is not None
                else None
            ),
        })

    return {
        "source": {
            "nesstar_path": str(nesstar_path),
        },
        "dataset": {
            "dataset_number": dataset.dataset_number,
            "file_id": f"dataset_{dataset.dataset_number:02d}",
            "file_name": (
                f"{embedded_dataset.file_name}.NSDstat"
                if embedded_dataset is not None
                else f"dataset_{dataset.dataset_number:02d}.NSDstat"
            ),
            "record_count": dataset.row_count,
            "var_count": dataset.variable_count,
        },
        "variables": variables_json,
    }


def _dataset_chunk_plan(
    data: bytes,
    dataset: Any,
    *,
    embedded_dataset: Any | None = None,
    use_category_labels: bool = False,
) -> tuple[list[str], list[ChunkReader]]:
    """Build headers and per-column readers for streaming dataset export."""
    offsets = dataset.variable_offsets_hint()
    if offsets is None:
        raise ValueError(f"Could not determine variable offsets for dataset {dataset.dataset_number}")

    offsets_by_name = {
        variable.name: (variable, start, size)
        for variable, start, size in offsets
    }
    ordered_names = _ordered_variable_names(dataset, embedded_dataset)

    headers: list[str] = []
    readers: list[ChunkReader] = []
    embedded_vars = {
        var.variable_name: var
        for var in (embedded_dataset.variables if embedded_dataset is not None else [])
    }
    for variable_name in ordered_names:
        variable, start, size = offsets_by_name[variable_name]
        headers.append(variable.name)
        if variable.is_binary_numeric:
            embedded_var = embedded_vars.get(variable.name)
            category_label_map = None
            if use_category_labels and embedded_var is not None and embedded_var.categories:
                category_label_map = _build_category_label_map(embedded_var.categories)
            readers.append(
                _build_compact_chunk_reader(
                    data,
                    start,
                    variable,
                    category_label_map=category_label_map,
                )
            )
            continue

        width = size // dataset.row_count if dataset.row_count else 0
        if width <= 0:
            raise ValueError(f"Invalid direct width for variable {variable.name!r}")
        readers.append(
            _build_nul_terminated_byte_string_chunk_reader(
                data,
                start,
                width,
            )
        )

    return headers, readers


def _write_dataset_csv(
    output_path: Path,
    data: bytes,
    dataset: Any,
    *,
    embedded_dataset: Any | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    delimiter: str = ",",
    include_header: bool = True,
    use_category_labels: bool = False,
) -> None:
    """Write one dataset to CSV or TSV, optionally gzip-compressed.

    CSV output uses Python's text-mode ``csv`` module so quoting and embedded
    line breaks are handled correctly. TSV output uses the binary path to
    preserve byte-oriented values and gzip behavior while writing CRLF rows.
    """
    headers, readers = _dataset_chunk_plan(
        data,
        dataset,
        embedded_dataset=embedded_dataset,
        use_category_labels=use_category_labels,
    )
    record_count = dataset.row_count

    if delimiter == "\t":
        delimiter_bytes = delimiter.encode("ascii")
        line_ending = b"\r\n"
        if output_path.suffix == ".gz":
            csv_context = gzip.open(output_path, "wb")
        else:
            csv_context = output_path.open("wb")
        with csv_context as csv_file:
            if include_header:
                header_row = delimiter_bytes.join(name.encode("utf-8") for name in headers) + line_ending
                csv_file.write(header_row)

            for row_start in range(0, record_count, chunk_size):
                rows_in_chunk = min(chunk_size, record_count - row_start)
                column_chunks = [reader(row_start, rows_in_chunk) for reader in readers]
                for row_offset in range(rows_in_chunk):
                    row = delimiter_bytes.join(
                        _format_output_value(column_chunk[row_offset])
                        for column_chunk in column_chunks
                    ) + line_ending
                    csv_file.write(row)
        return

    if output_path.suffix == ".gz":
        csv_context = gzip.open(output_path, "wt", encoding="utf-8", errors="surrogateescape", newline="")
    else:
        csv_context = output_path.open("w", encoding="utf-8", errors="surrogateescape", newline="")
    with csv_context as csv_file:
        writer = csv.writer(csv_file, delimiter=delimiter, lineterminator="\r\n")
        if include_header:
            writer.writerow(headers)

        for row_start in range(0, record_count, chunk_size):
            rows_in_chunk = min(chunk_size, record_count - row_start)
            column_chunks = [reader(row_start, rows_in_chunk) for reader in readers]
            for row_offset in range(rows_in_chunk):
                writer.writerow(
                    _format_output_text(column_chunk[row_offset])
                    for column_chunk in column_chunks
                )


def export_nesstar_to_csv_and_json(
    nesstar_path: str | Path,
    *,
    output_prefix: str | Path | None = None,
    output_dir: str | Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    delimiter: str = ",",
    include_header: bool = True,
    compressed: bool = False,
    use_category_labels: bool = False,
) -> list[dict[str, str]]:
    """Export every dataset in a NESSTAR container to CSV plus metadata JSON."""
    if (output_prefix is None) == (output_dir is None):
        raise ValueError("Provide exactly one of output_prefix or output_dir")

    nesstar_path = Path(nesstar_path).resolve()
    parsed = parse_nesstar_binary(nesstar_path)
    embedded = parse_embedded_dataset_metadata(nesstar_path)
    data = nesstar_path.read_bytes()
    embedded_datasets = {dataset.dataset_number: dataset for dataset in embedded.datasets}

    if output_dir is not None:
        base_dir = Path(output_dir).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        prefix_base = base_dir / nesstar_path.stem
    else:
        prefix_base = Path(output_prefix).resolve()
        prefix_base.parent.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, str]] = []
    for dataset in parsed.datasets:
        embedded_dataset = embedded_datasets.get(dataset.dataset_number)
        stem = _dataset_output_stem(
            prefix_base,
            dataset.dataset_number,
            embedded_dataset.file_name
            if embedded_dataset is not None
            else f"dataset_{dataset.dataset_number:02d}",
        )
        data_suffix = ".tsv" if delimiter == "\t" else ".csv"
        if compressed:
            data_suffix = f"{data_suffix}.gz"
        data_path = _append_suffix(stem, data_suffix)
        json_path = _append_suffix(stem, ".json")

        _write_dataset_csv(
            data_path,
            data,
            dataset,
            embedded_dataset=embedded_dataset,
            chunk_size=chunk_size,
            delimiter=delimiter,
            include_header=include_header,
            use_category_labels=use_category_labels,
        )

        metadata_json = _build_dataset_metadata_json(
            dataset,
            embedded_dataset,
            nesstar_path,
        )
        with json_path.open("w", encoding="utf-8") as json_file:
            json.dump(metadata_json, json_file, ensure_ascii=False, indent=2)
            json_file.write("\n")

        written.append({
            "dataset_number": str(dataset.dataset_number),
            "data": str(data_path),
            "json": str(json_path),
        })

    return written
