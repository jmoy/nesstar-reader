from __future__ import annotations

import pytest

from ddi_metadata import DatasetMetadata
from nesstar_reader.binary import ParsedNesstarBinary, decode_variable_values_hint


def test_all_decoded_compact_numeric_variables_match_xml_summary_stats(
    parsed_binary: ParsedNesstarBinary,
    parsed_metadata: DatasetMetadata | None,
    nesstar_bytes: bytes,
) -> None:
    if parsed_metadata is None:
        pytest.skip("XML metadata not provided")
    metadata_files = sorted(parsed_metadata.files.values(), key=lambda file_desc: (file_desc.index, file_desc.id))

    checked = 0
    for dataset, metadata_file in zip(parsed_binary.datasets, metadata_files, strict=True):
        offsets = dataset.variable_offsets_hint()
        assert offsets is not None, f"dataset {dataset.dataset_number}"
        metadata_vars = {var.name: var for var in metadata_file.variables}
        for variable, start, size in offsets:
            if not variable.is_binary_numeric:
                continue
            metadata_var = metadata_vars.get(variable.name)
            if metadata_var is None:
                continue
            if (
                metadata_var.stats.min is None
                or metadata_var.stats.max is None
                or metadata_var.stats.mean is None
            ):
                continue

            decoded = decode_variable_values_hint(nesstar_bytes, dataset, variable, start, size)
            if decoded is None:
                continue
            non_missing = [value for value in decoded if value is not None]
            assert non_missing, variable.name

            checked += 1
            assert min(non_missing) == metadata_var.stats.min, variable.name
            assert max(non_missing) == metadata_var.stats.max, variable.name
            assert round(sum(non_missing) / len(non_missing) - metadata_var.stats.mean, 3) == 0, variable.name

    assert checked > 0
