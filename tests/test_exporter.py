from __future__ import annotations

import csv
import gzip
from pathlib import Path
from types import SimpleNamespace

from nesstar_reader.exporter import (
    _append_suffix,
    _build_category_label_map,
    _build_compact_chunk_reader,
    _build_nul_terminated_byte_string_chunk_reader,
    _dataset_output_stem,
    _ordered_variable_names,
    _write_dataset_csv,
)


def test_ordered_variable_names_follow_embedded_metadata() -> None:
    dataset = SimpleNamespace(
        variables=[
            SimpleNamespace(name="c"),
            SimpleNamespace(name="a"),
            SimpleNamespace(name="b"),
        ]
    )
    embedded_dataset = SimpleNamespace(
        variables=[
            SimpleNamespace(variable_name="a"),
            SimpleNamespace(variable_name="b"),
        ]
    )

    assert _ordered_variable_names(dataset, embedded_dataset) == ["a", "b", "c"]


def test_nul_terminated_byte_string_chunk_reader_can_preserve_textual_numeric_formatting() -> None:
    reader = _build_nul_terminated_byte_string_chunk_reader(
        b"030712",
        0,
        2,
    )

    assert reader(0, 3) == [b"03", b"07", b"12"]


def test_nul_terminated_byte_string_chunk_reader_preserves_spaces_before_terminator() -> None:
    reader = _build_nul_terminated_byte_string_chunk_reader(
        b"A \x00B  ",
        0,
        3,
    )

    assert reader(0, 2) == [b"A ", b"B  "]


def test_nul_terminated_byte_string_chunk_reader_treats_all_nul_cells_as_empty() -> None:
    reader = _build_nul_terminated_byte_string_chunk_reader(
        b"\x00\x00\x00ABC",
        0,
        3,
    )

    assert reader(0, 2) == [b"", b"ABC"]


def test_nul_terminated_byte_string_chunk_reader_stops_at_first_nul() -> None:
    reader = _build_nul_terminated_byte_string_chunk_reader(
        b"7\x008\x00",
        0,
        2,
    )

    assert reader(0, 2) == [b"7", b"8"]


def test_dataset_output_stem_uses_embedded_file_name_verbatim(tmp_path: Path) -> None:
    stem = _dataset_output_stem(tmp_path / "input_stem", 3, "LEVEL - 01(Section 1 and 1.1)")

    assert stem == tmp_path / "LEVEL - 01(Section 1 and 1.1)"


def test_dataset_output_stem_strips_embedded_path_components(tmp_path: Path) -> None:
    assert _dataset_output_stem(tmp_path / "input_stem", 3, "../outside") == tmp_path / "outside"
    assert _dataset_output_stem(tmp_path / "input_stem", 3, "/tmp/outside") == tmp_path / "outside"
    assert _dataset_output_stem(tmp_path / "input_stem", 3, r"..\outside") == tmp_path / "outside"


def test_append_suffix_preserves_embedded_dots_in_file_name(tmp_path: Path) -> None:
    path = tmp_path / "LEVEL - 01(Section 1 and 1.1)"

    assert _append_suffix(path, ".tsv") == tmp_path / "LEVEL - 01(Section 1 and 1.1).tsv"


def test_write_dataset_csv_supports_gzip_output(tmp_path: Path) -> None:
    dataset = SimpleNamespace(
        dataset_number=1,
        row_count=2,
        variables=[SimpleNamespace(name="code", is_binary_numeric=False)],
        variable_offsets_hint=lambda: [
            (SimpleNamespace(name="code", is_binary_numeric=False), 0, 4),
        ],
    )

    output_path = tmp_path / "sample.tsv.gz"
    _write_dataset_csv(
        output_path,
        b"0102",
        dataset,
        delimiter="\t",
        include_header=False,
    )

    with gzip.open(output_path, "rb") as handle:
        assert handle.read() == b"01\r\n02\r\n"


def test_write_dataset_csv_escapes_comma_delimited_fields(tmp_path: Path) -> None:
    dataset = SimpleNamespace(
        dataset_number=1,
        row_count=2,
        variables=[
            SimpleNamespace(name="code", is_binary_numeric=False),
            SimpleNamespace(name="label", is_binary_numeric=False),
        ],
        variable_offsets_hint=lambda: [
            (SimpleNamespace(name="code", is_binary_numeric=False), 0, 3 * 2),
            (SimpleNamespace(name="label", is_binary_numeric=False), 6, 6 * 2),
        ],
    )

    output_path = tmp_path / "sample.csv"
    _write_dataset_csv(
        output_path,
        b'A,BC"DLine\n1plain\x00',
        dataset,
    )

    with output_path.open("r", encoding="utf-8", newline="") as handle:
        assert list(csv.reader(handle)) == [
            ["code", "label"],
            ["A,B", "Line\n1"],
            ['C"D', "plain"],
        ]


def test_category_label_map_normalizes_zero_padded_numeric_values() -> None:
    categories = [
        SimpleNamespace(value="01", label="Jan"),
        SimpleNamespace(value="02", label="Feb"),
    ]

    mapping = _build_category_label_map(categories)

    assert mapping[1] == b"Jan"
    assert mapping[2] == b"Feb"


def test_compact_chunk_reader_can_replace_numeric_codes_with_category_labels() -> None:
    variable = SimpleNamespace(
        value_family="byte-coded",
        additive_offset=None,
        missing_value_code=0xFF,
        name="month",
    )
    reader = _build_compact_chunk_reader(
        b"\x01\x02\xff",
        0,
        variable,
        category_label_map={1: b"Jan", 2: b"Feb"},
    )

    assert reader(0, 3) == [b"Jan", b"Feb", None]
