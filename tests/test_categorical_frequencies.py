"""Tests that decoded compact categories match external DDI frequencies."""

from __future__ import annotations

from collections import Counter

import pytest

from nesstar_reader.binary import ParsedNesstarBinary, decode_variable_values_hint
from tests.ddi_metadata import DatasetMetadata


def test_decoded_categorical_frequencies_match_xml(
    parsed_binary: ParsedNesstarBinary,
    parsed_metadata: DatasetMetadata | None,
    nesstar_bytes: bytes,
) -> None:
    """For every compact variable with complete DDI categories, compare non-missing frequencies."""
    if parsed_metadata is None:
        pytest.skip("XML metadata not provided")
    metadata_files = sorted(parsed_metadata.files.values(), key=lambda file_desc: (file_desc.index, file_desc.id))

    checked = 0
    for dataset, metadata_file in zip(parsed_binary.datasets, metadata_files, strict=True):
        offsets = dataset.variable_offsets_hint()
        assert offsets is not None, f"dataset {dataset.dataset_number}"
        metadata_vars = {
            var.name: var
            for var in metadata_file.variables
        }
        for variable, start, size in offsets:
            if not variable.is_binary_numeric:
                continue
            mv = metadata_vars.get(variable.name)
            if mv is None or not mv.categories:
                continue
            ddi_counts = Counter({
                int(cat.value): cat.frequency
                for cat in mv.categories
                if cat.value != "Sysmiss"
            })
            if not ddi_counts:
                continue
            if sum(ddi_counts.values()) != mv.stats.valid_count:
                continue

            decoded = decode_variable_values_hint(
                nesstar_bytes, dataset, variable, start, size,
            )
            if decoded is None:
                continue

            non_missing = [v for v in decoded if v is not None]
            actual_counts = Counter(non_missing)
            checked += 1
            assert actual_counts == ddi_counts, f"{variable.name} in dataset {dataset.dataset_number}"

    assert checked > 0
