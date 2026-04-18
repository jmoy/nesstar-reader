"""Open source extractor for NESSTAR/NSDstat data files."""

from .binary import (
	decode_compact_values_with_hints,
	decode_compact_values_hint,
	decode_embedded_metadata_block,
	decode_header_metadata_blocks,
	decode_variable_values_hint,
	discover_descriptor_section_offset,
	parse_embedded_categories,
	parse_embedded_dataset_metadata,
	parse_embedded_file_description_name,
	parse_embedded_stat_options,
	parse_nesstar_binary,
	scan_trailing_metadata_blocks,
	unpack_packed_nibbles,
)

__version__ = "0.1.0"

__all__ = [
	"decode_compact_values_with_hints",
	"decode_compact_values_hint",
	"decode_embedded_metadata_block",
	"decode_header_metadata_blocks",
	"decode_variable_values_hint",
	"discover_descriptor_section_offset",
	"parse_embedded_categories",
	"parse_embedded_dataset_metadata",
	"parse_embedded_file_description_name",
	"parse_embedded_stat_options",
	"parse_nesstar_binary",
	"scan_trailing_metadata_blocks",
	"unpack_packed_nibbles",
	"__version__",
]
