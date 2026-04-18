"""Core data structures for parsed NESSTAR containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import struct
from pathlib import Path

from .constants import (
    COMPACT_WIDTH_CODE_ENCODING_FAMILIES,
    COMPACT_WIDTH_CODE_PHYSICAL_WIDTHS,
)


@dataclass(slots=True)
class EmbeddedMetadataBlock:
    """Decoded static-Huffman XML block and its source payload coordinates."""

    offset: int
    symbol_count: int
    output_length: int
    payload_offset: int
    payload_length: int
    decoded_xml: str
    dataset_index: int | None = None
    ascii_prefix: str = ""

    @property
    def xml_root_tag(self) -> str | None:
        """Return the first XML element tag after the declaration, if present."""
        start = self.decoded_xml.find("<", 1)
        if start == -1:
            return None
        end = start + 1
        while end < len(self.decoded_xml) and self.decoded_xml[end].isalnum():
            end += 1
        return self.decoded_xml[start + 1 : end] or None


@dataclass(slots=True)
class EmbeddedCategory:
    """Categorical value label recovered from an embedded Categories block."""

    value: str
    label: str


@dataclass(slots=True)
class EmbeddedStatOptions:
    """Boolean summary-stat flags exposed by an embedded ExtVarInf block."""

    min_enabled: bool
    max_enabled: bool
    mean_enabled: bool
    stddev_enabled: bool
    mean_weighted_enabled: bool
    stddev_weighted_enabled: bool


@dataclass(slots=True)
class VariableEmbeddedMetadata:
    """Resolved embedded XML and text metadata for one variable."""

    variable_name: str
    variable_id: int
    label: str
    width_value: int
    object_id: int
    label_resource_id: int
    category_resource_id: int
    ext_var_inf_block: EmbeddedMetadataBlock | None = None
    categories_block: EmbeddedMetadataBlock | None = None
    stat_options: EmbeddedStatOptions | None = None
    categories: list[EmbeddedCategory] = field(default_factory=list)


@dataclass(slots=True)
class DatasetEmbeddedMetadata:
    """Resolved embedded metadata for one dataset inside the container."""

    dataset_number: int
    file_description_block: EmbeddedMetadataBlock
    file_name: str
    record_count: int
    var_count: int
    variables: list[VariableEmbeddedMetadata] = field(default_factory=list)


@dataclass(slots=True)
class EmbeddedTemplateReference:
    """One manifest entry pointing to a plain XML template resource."""

    name: str
    record_id: int


@dataclass(slots=True)
class EmbeddedTemplateDocument:
    """Plain XML template document resolved from the template manifest."""

    record_id: int
    name: str
    root_tag: str
    version: str
    author: str
    organization: str
    xml_text: str = field(repr=False)
    tab_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedEmbeddedMetadata:
    """Top-level embedded metadata view assembled from XML and text resources."""

    title: str
    document_id: str
    doc_description_block: EmbeddedMetadataBlock | None
    study_description_block: EmbeddedMetadataBlock | None
    template_manifest: list[EmbeddedTemplateReference]
    template_documents: list[EmbeddedTemplateDocument]
    datasets: list[DatasetEmbeddedMetadata]

    def dataset(self, dataset_number: int) -> DatasetEmbeddedMetadata:
        """Return the embedded metadata object for a dataset number."""
        return next(ds for ds in self.datasets if ds.dataset_number == dataset_number)

    def variable(self, name: str) -> VariableEmbeddedMetadata:
        """Return the first embedded variable metadata object with the given name."""
        return next(var for ds in self.datasets for var in ds.variables if var.variable_name == name)


@dataclass(slots=True)
class TrailingResourceIndexRecord:
    """One resource-index row mapping a record id to payload bytes."""

    record_id: int
    target_offset: int
    length: int


@dataclass(slots=True)
class VariableDirectoryEntry:
    """Parsed variable-directory entry describing storage for one column."""

    entry_index: int
    name: str
    width_value: int
    variable_id: int
    label_resource_id: int
    category_resource_id: int
    object_id: int
    mode_code: int
    value_format_code: int
    value_offset_i64: int

    @property
    def is_binary_numeric(self) -> bool:
        """Return whether the variable uses compact binary numeric storage."""
        return self.mode_code == 5

    @property
    def value_family(self) -> str | None:
        """Map the NESSTAR value-format code to a decoder family name."""
        if not self.is_binary_numeric:
            return None
        return COMPACT_WIDTH_CODE_ENCODING_FAMILIES.get(self.value_format_code)

    @property
    def missing_value_code(self) -> int | float | None:
        """Return the raw storage sentinel used for missing compact values."""
        family = self.value_family
        if family == "nibble-packed":
            return 0x0F
        if family == "byte-coded":
            return 0xFF
        if family == "uint16":
            return 0xFFFF
        if family == "uint24":
            return 0xFFFFFF
        if family == "uint32":
            return 0xFFFFFFFF
        if family == "uint40":
            return 0xFFFFFFFFFF
        if family == "float64":
            return struct.unpack("<d", b"\xff\xff\xff\xff\xff\xff\xef\x7f")[0]
        return None

    @property
    def additive_offset(self) -> int | None:
        """Return the signed bias applied to non-floating compact values."""
        if not self.is_binary_numeric:
            return None
        if self.value_family == "float64":
            return None
        if self.value_offset_i64 == 0:
            return None
        return self.value_offset_i64

    @property
    def bytes_per_row_hint(self) -> Fraction | None:
        """Return the physical byte width implied by the directory entry."""
        if not self.is_binary_numeric:
            return Fraction(self.width_value, 1)
        return COMPACT_WIDTH_CODE_PHYSICAL_WIDTHS.get(self.value_format_code)

    def physical_size(self, record_count: int) -> int | None:
        """Return the encoded byte size for a variable with known row count."""
        width = self.bytes_per_row_hint
        if width is None:
            return None
        if width == Fraction(1, 2):
            return (record_count + 1) // 2
        size = width * record_count
        if size.denominator != 1:
            return None
        return size.numerator


@dataclass(slots=True)
class DatasetDescriptor:
    """Parsed descriptor plus resolved directory and data-region details."""

    dataset_number: int
    variable_count: int
    row_count: int
    file_description_record_id: int
    variable_directory_entry_size: int
    variable_directory_record_id: int
    directory_offset: int | None = None
    data_start_offset: int | None = None
    data_end_offset: int | None = None
    indexed_variable_offsets: dict[int, int] = field(default_factory=dict)
    indexed_variable_lengths: dict[int, int] = field(default_factory=dict)
    variables: list[VariableDirectoryEntry] = field(default_factory=list)

    def direct_data_size(self) -> int:
        """Return the bytes occupied by direct string columns with known widths."""
        total = 0
        for variable in self.variables:
            if variable.is_binary_numeric:
                continue
            width = variable.bytes_per_row_hint
            if width is None:
                return total
            size = width * self.row_count
            if size.denominator != 1:
                return total
            total += size.numerator
        return total

    def compact_data_budget(self) -> int | None:
        """Return the data-region bytes left after direct string columns."""
        if self.data_start_offset is None or self.data_end_offset is None:
            return None
        total = self.data_end_offset - self.data_start_offset + 1
        return total - self.direct_data_size()

    def reconcile_compact_physical_widths(self) -> dict[str, Fraction] | None:
        """Infer compact widths when exactly one binary variable lacks a hint.

        Modern files usually expose each variable payload through the trailing
        resource index, so callers can use indexed lengths directly. This helper
        remains useful for older hypotheses and tests that only have the total
        dataset data region; it solves the one-unknown case from the remaining
        byte budget.
        """
        budget = self.compact_data_budget()
        if budget is None:
            return None

        known: dict[str, Fraction] = {}
        unknown: list[VariableDirectoryEntry] = []

        for variable in self.variables:
            if not variable.is_binary_numeric:
                continue
            width = variable.bytes_per_row_hint
            if width is None:
                unknown.append(variable)
                continue
            known[variable.name] = width

        if not unknown:
            return known
        if len(unknown) != 1:
            return None

        used = 0
        for variable in self.variables:
            if not variable.is_binary_numeric or variable.name not in known:
                continue
            size = variable.physical_size(self.row_count)
            if size is None:
                return None
            used += size
        remaining = Fraction(budget - used, 1)
        if remaining == -1:
            known[unknown[0].name] = Fraction(0, 1)
            return known
        solved = remaining / self.row_count
        if solved < 0:
            return None
        known[unknown[0].name] = solved
        return known

    def variable_offsets_hint(self) -> list[tuple[VariableDirectoryEntry, int, int]] | None:
        """Return ordered ``(variable, start, size)`` payload spans for a dataset.

        The implementation prefers exact offsets and lengths from the trailing
        resource index because the recovered format documentation treats those
        records as authoritative for variable payloads. The older sequential
        width-based reconstruction is retained as a fallback for descriptors
        that do not carry indexed spans.
        """
        if self.data_start_offset is None:
            return None

        if self.variables:
            assert len(self.indexed_variable_offsets) == len(self.variables), (
                f"Dataset {self.dataset_number} is missing indexed variable offsets"
            )
            assert len(self.indexed_variable_lengths) == len(self.variables), (
                f"Dataset {self.dataset_number} is missing indexed variable lengths"
            )
            result: list[tuple[VariableDirectoryEntry, int, int]] = []
            for index, variable in enumerate(self.variables):
                start = self.indexed_variable_offsets[variable.variable_id]
                size = self.indexed_variable_lengths[variable.variable_id]
                assert size >= 0, f"Dataset {self.dataset_number} variable {variable.variable_id} has negative size"
                if index + 1 < len(self.variables):
                    next_start = self.indexed_variable_offsets[self.variables[index + 1].variable_id]
                    assert start + size == next_start, (
                        f"Dataset {self.dataset_number} variable {variable.variable_id} "
                        f"ends at {start + size:#x} but next variable starts at {next_start:#x}"
                    )
                elif self.data_end_offset is not None:
                    assert start + size - 1 == self.data_end_offset, (
                        f"Dataset {self.dataset_number} last variable {variable.variable_id} "
                        f"ends at {start + size - 1:#x} but dataset data_end_offset is {self.data_end_offset:#x}"
                    )
                result.append((variable, start, size))
            return result

        reconciled_widths = self.reconcile_compact_physical_widths() or {}
        result: list[tuple[VariableDirectoryEntry, int, int]] = []
        offset = self.data_start_offset
        for variable in self.variables:
            if variable.name in reconciled_widths:
                width = reconciled_widths[variable.name]
                if width == Fraction(1, 2):
                    size = (self.row_count + 1) // 2
                else:
                    size_fraction = width * self.row_count
                    if size_fraction.denominator != 1:
                        return None
                    size = size_fraction.numerator
            else:
                size = variable.physical_size(self.row_count)
            if size is None:
                return None
            result.append((variable, offset, size))
            offset += size
        if self.data_end_offset is not None and result:
            remaining = self.data_end_offset + 1 - offset
            if abs(remaining) > 1:
                return None
            if remaining != 0:
                variable, start, size = result[-1]
                adjusted = size + remaining
                if adjusted < 0:
                    return None
                result[-1] = (variable, start, adjusted)
        return result


@dataclass(slots=True)
class ParsedNesstarBinary:
    """Parsed binary container layout without materialized column values."""

    path: Path
    file_size: int
    version_bytes: bytes
    dataset_count_hint: int
    datasets: list[DatasetDescriptor]
    trailing_metadata_start_offset: int | None = None
    trailing_metadata_end_offset: int | None = None
    trailing_resource_index: dict[int, TrailingResourceIndexRecord] = field(default_factory=dict)


class NesstarBinaryFormatError(ValueError):
    """Raised when a file does not match the currently understood container shape."""
