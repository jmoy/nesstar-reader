"""Format-level constants shared across parser modules."""

from __future__ import annotations

from fractions import Fraction


MAGIC = b"NESSTART"
NAME_OFFSET_IN_ENTRY = 63
NAME_UTF16LE_BYTES = 64
TRAILING_RESOURCE_INDEX_RECORD_SIZE = 15

HEADER_RESOURCE_INDEX_OFFSET = 0x25
HEADER_DATASET_COUNT = 0x2B
HEADER_DESCRIPTOR_RECORD_SIZE = 0x2D
HEADER_BASE_RECORD_ID = 0x2F
HEADER_TEMPLATE_MANIFEST_ID = 0x4F

HEADER_METADATA_BLOCK_1_RECORD_ID = 1
HEADER_METADATA_BLOCK_2_RECORD_ID = 2

COMPACT_WIDTH_CODE_PHYSICAL_WIDTHS: dict[int, Fraction] = {
    2: Fraction(1, 2),
    3: Fraction(1, 1),
    4: Fraction(2, 1),
    5: Fraction(3, 1),
    6: Fraction(4, 1),
    7: Fraction(5, 1),
    10: Fraction(8, 1),
}

COMPACT_WIDTH_CODE_ENCODING_FAMILIES: dict[int, str] = {
    2: "nibble-packed",
    3: "byte-coded",
    4: "uint16",
    5: "uint24",
    6: "uint32",
    7: "uint40",
    10: "float64",
}
