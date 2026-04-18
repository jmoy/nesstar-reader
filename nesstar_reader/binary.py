"""Compatibility facade for the hierarchical NESSTAR parser modules."""

from __future__ import annotations

from .binary_format.decoders.compact import (
    apply_missing_sentinel_hint,
    apply_value_bias_hint,
    decode_compact_values_hint,
    decode_compact_values_with_hints,
    decode_variable_values_hint,
    unpack_packed_nibbles,
)
from .binary_format.decoders.huffman import decode_embedded_metadata_block
from .binary_format.decoders.text import decode_text_resource as _decode_text_resource
from .binary_format.layout import discover_trailing_metadata_bounds as _discover_trailing_metadata_bounds
from .binary_format.layout import parse_nesstar_binary
from .binary_format.parsers.descriptors import discover_descriptor_section_offset, parse_descriptors as _parse_descriptors
from .binary_format.parsers.directory import (
    parse_directory_entry as _parse_directory_entry,
    validate_directory as _validate_directory,
)
from .binary_format.parsers.embedded_metadata import (
    decode_header_metadata_blocks,
    decode_indexed_metadata_block,
    parse_embedded_categories,
    parse_embedded_dataset_metadata,
    parse_embedded_file_description_name,
    parse_embedded_stat_options,
    parse_embedded_template_manifest,
    parse_embedded_title_and_id,
    parse_plain_xml_template_documents,
    scan_trailing_metadata_blocks,
    xml_bool as _xml_bool,
    xml_root as _xml_root,
)
from .binary_format.parsers.resource_index import parse_trailing_resource_index
from .binary_format.types import (
    DatasetDescriptor,
    DatasetEmbeddedMetadata,
    EmbeddedCategory,
    EmbeddedMetadataBlock,
    EmbeddedStatOptions,
    EmbeddedTemplateDocument,
    EmbeddedTemplateReference,
    NesstarBinaryFormatError,
    ParsedEmbeddedMetadata,
    ParsedNesstarBinary,
    TrailingResourceIndexRecord,
    VariableDirectoryEntry,
    VariableEmbeddedMetadata,
)
from .binary_format.utils import (
    decode_directory_name as _decode_directory_name,
    is_plausible_variable_name as _is_plausible_variable_name,
    u16le as _u16le,
    u32le as _u32le,
)


__all__ = [
    "DatasetDescriptor",
    "DatasetEmbeddedMetadata",
    "EmbeddedCategory",
    "EmbeddedMetadataBlock",
    "EmbeddedStatOptions",
    "EmbeddedTemplateDocument",
    "EmbeddedTemplateReference",
    "NesstarBinaryFormatError",
    "ParsedEmbeddedMetadata",
    "ParsedNesstarBinary",
    "TrailingResourceIndexRecord",
    "VariableDirectoryEntry",
    "VariableEmbeddedMetadata",
    "apply_missing_sentinel_hint",
    "apply_value_bias_hint",
    "decode_compact_values_hint",
    "decode_compact_values_with_hints",
    "decode_embedded_metadata_block",
    "decode_header_metadata_blocks",
    "decode_indexed_metadata_block",
    "decode_variable_values_hint",
    "discover_descriptor_section_offset",
    "parse_embedded_categories",
    "parse_embedded_dataset_metadata",
    "parse_embedded_file_description_name",
    "parse_embedded_stat_options",
    "parse_embedded_template_manifest",
    "parse_embedded_title_and_id",
    "parse_nesstar_binary",
    "parse_plain_xml_template_documents",
    "parse_trailing_resource_index",
    "scan_trailing_metadata_blocks",
    "unpack_packed_nibbles",
]
