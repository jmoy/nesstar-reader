"""Tests comparing embedded NESSTAR metadata with external DDI XML."""

from __future__ import annotations

import pytest

from ddi_metadata import DatasetMetadata
from nesstar_reader.binary import ParsedEmbeddedMetadata


def _normalize_text(value: str) -> str:
    """Collapse whitespace for cross-source metadata comparisons."""
    return " ".join(value.split())


def test_embedded_title_matches_external_xml(
    embedded_metadata: ParsedEmbeddedMetadata,
    parsed_metadata: DatasetMetadata | None,
) -> None:
    """Compare embedded title and document id with DDI XML."""
    if parsed_metadata is None:
        pytest.skip("XML metadata not provided")
    assert embedded_metadata.title == parsed_metadata.title
    assert embedded_metadata.document_id == parsed_metadata.id


def test_dataset_file_names_and_dimensions_match_external_xml(
    embedded_metadata: ParsedEmbeddedMetadata,
    parsed_metadata: DatasetMetadata | None,
) -> None:
    """Compare embedded dataset names and dimensions with DDI XML."""
    if parsed_metadata is None:
        pytest.skip("XML metadata not provided")
    for dataset in embedded_metadata.datasets:
        ext_file = next(
            fd for fd in parsed_metadata.files.values()
            if fd.name.removesuffix(".NSDstat") == dataset.file_name
        )
        assert dataset.record_count == ext_file.record_count
        assert dataset.var_count == ext_file.var_count


def test_embedded_labels_widths_and_categories_match_external_xml(
    embedded_metadata: ParsedEmbeddedMetadata,
    parsed_metadata: DatasetMetadata | None,
) -> None:
    """Compare embedded variable labels, widths, and categories with DDI XML."""
    if parsed_metadata is None:
        pytest.skip("XML metadata not provided")
    for dataset in embedded_metadata.datasets:
        ext_file = next(
            fd for fd in parsed_metadata.files.values()
            if fd.name.removesuffix(".NSDstat") == dataset.file_name
        )
        ext_vars = {
            var.name: var
            for var in ext_file.variables
        }
        for variable in dataset.variables:
            ext = ext_vars[variable.variable_name]
            assert _normalize_text(variable.label) == _normalize_text(ext.label), variable.variable_name
            assert variable.width_value == ext.width, variable.variable_name
            if variable.categories:
                embedded_cats = {
                    (c.value, _normalize_text(c.label))
                    for c in variable.categories
                }
                ext_cats = {
                    (c.value, _normalize_text(c.label))
                    for c in ext.categories
                    if c.value in {ec.value for ec in variable.categories}
                }
                assert embedded_cats == ext_cats, variable.variable_name
