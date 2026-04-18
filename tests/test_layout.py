"""Tests for parsing dataset layout and variable payload offsets."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from ddi_metadata import DatasetMetadata
from nesstar_reader.binary import DatasetDescriptor, ParsedNesstarBinary


def test_parser_produces_correct_dataset_count(
    parsed_binary: ParsedNesstarBinary,
    parsed_metadata: DatasetMetadata | None,
) -> None:
    """Compare parsed dataset count with external DDI metadata."""
    if parsed_metadata is None:
        pytest.skip("XML metadata not provided")
    assert len(parsed_binary.datasets) == len(parsed_metadata.files)


def test_variable_names_match_external_xml(
    parsed_binary: ParsedNesstarBinary,
    parsed_metadata: DatasetMetadata | None,
) -> None:
    """Compare variable order and names with external DDI metadata."""
    if parsed_metadata is None:
        pytest.skip("XML metadata not provided")
    binary_names = [
        var.name
        for dataset in parsed_binary.datasets
        for var in dataset.variables
    ]
    xml_names = [
        var.name
        for fd in sorted(parsed_metadata.files.values(), key=lambda f: (f.index, f.id))
        for var in fd.variables
    ]
    assert binary_names == xml_names


def test_variable_sizes_sum_to_data_region(parsed_binary: ParsedNesstarBinary) -> None:
    """Check that per-variable payload sizes cover each dataset data region."""
    for dataset in parsed_binary.datasets:
        offsets = dataset.variable_offsets_hint()
        assert offsets is not None, f"dataset {dataset.dataset_number}"
        total = sum(size for _, _, size in offsets)
        actual = dataset.data_end_offset - dataset.data_start_offset + 1
        assert total == actual, f"dataset {dataset.dataset_number}"


def test_variable_offsets_prefer_indexed_lengths_when_available() -> None:
    """Confirm indexed resource lengths win over width-based reconstruction."""
    dataset = DatasetDescriptor(
        dataset_number=1,
        variable_count=2,
        row_count=10,
        file_description_record_id=0,
        variable_directory_entry_size=160,
        variable_directory_record_id=100,
        data_start_offset=1000,
        data_end_offset=1024,
        indexed_variable_offsets={101: 1000, 102: 1008},
        indexed_variable_lengths={101: 8, 102: 17},
        variables=[
            SimpleNamespace(variable_id=101),
            SimpleNamespace(variable_id=102),
        ],
    )

    offsets = dataset.variable_offsets_hint()

    assert offsets is not None
    assert [(start, size) for _, start, size in offsets] == [(1000, 8), (1008, 17)]
