"""Column-value decoders derived from compact storage descriptors."""

from __future__ import annotations

import struct

from ..types import DatasetDescriptor, VariableDirectoryEntry


def unpack_packed_nibbles(data: bytes, record_count: int) -> list[int]:
    """Decode high-then-low 4-bit values from a compact numeric payload."""
    values: list[int] = []
    for byte in data[: (record_count + 1) // 2]:
        values.append((byte >> 4) & 0x0F)
        values.append(byte & 0x0F)
    return values[:record_count]


def _decode_uint16_values(data: bytes, record_count: int) -> list[int]:
    """Decode little-endian unsigned 16-bit compact values."""
    return [int.from_bytes(data[i : i + 2], "little") for i in range(0, min(len(data), record_count * 2), 2)]


def _decode_uint24_values(data: bytes, record_count: int) -> list[int]:
    """Decode little-endian unsigned 24-bit compact values."""
    return [int.from_bytes(data[i : i + 3], "little") for i in range(0, min(len(data), record_count * 3), 3)]


def _decode_uint32_values(data: bytes, record_count: int) -> list[int]:
    """Decode little-endian unsigned 32-bit compact values."""
    return [int.from_bytes(data[i : i + 4], "little") for i in range(0, min(len(data), record_count * 4), 4)]


def _decode_uint40_values(data: bytes, record_count: int) -> list[int]:
    """Decode little-endian unsigned 40-bit compact values."""
    return [int.from_bytes(data[i : i + 5], "little") for i in range(0, min(len(data), record_count * 5), 5)]


def _decode_float64_values(data: bytes, record_count: int) -> list[float]:
    """Decode little-endian IEEE-754 double compact values."""
    return [
        struct.unpack("<d", data[i : i + 8])[0]
        for i in range(0, min(len(data), record_count * 8), 8)
    ]


def decode_compact_values_hint(
    data: bytes,
    variable: VariableDirectoryEntry,
    record_count: int,
) -> list[int | float] | None:
    """Decode raw compact values using the variable's format-code hint.

    Missing-value sentinels and additive integer offsets are deliberately left
    untouched here so callers can inspect raw storage values. Use
    ``decode_compact_values_with_hints`` when the decoded values should match
    logical survey values.
    """
    family = variable.value_family
    if family == "nibble-packed":
        return unpack_packed_nibbles(data, record_count)
    if family == "byte-coded":
        return list(data[:record_count])
    if family == "uint16":
        return _decode_uint16_values(data, record_count)
    if family == "uint24":
        return _decode_uint24_values(data, record_count)
    if family == "uint32":
        return _decode_uint32_values(data, record_count)
    if family == "uint40":
        return _decode_uint40_values(data, record_count)
    if family == "float64":
        return _decode_float64_values(data, record_count)
    return None


def apply_missing_sentinel_hint(values: list[int | float], variable: VariableDirectoryEntry) -> list[int | float | None]:
    """Replace the variable's raw missing-value sentinel with ``None``."""
    missing_value_code = variable.missing_value_code
    if missing_value_code is None:
        return values
    return [None if value == missing_value_code else value for value in values]


def apply_value_bias_hint(values: list[int], variable: VariableDirectoryEntry) -> list[int]:
    """Apply the variable's signed additive offset to decoded integer values."""
    additive_offset = variable.additive_offset
    if additive_offset is None:
        return values
    return [value + additive_offset for value in values]


def decode_compact_values_with_hints(
    data: bytes,
    variable: VariableDirectoryEntry,
    record_count: int,
) -> list[int | float | None] | None:
    """Decode compact values and apply known missing and offset semantics."""
    values = decode_compact_values_hint(data, variable, record_count)
    if values is None:
        return None
    values_with_missing = apply_missing_sentinel_hint(values, variable)
    additive_offset = variable.additive_offset
    if additive_offset is None:
        return values_with_missing
    return [None if value is None else value + additive_offset for value in values_with_missing]


def decode_variable_values_hint(
    data: bytes,
    dataset: DatasetDescriptor,
    variable: VariableDirectoryEntry,
    start: int,
    size: int,
) -> list[int | float | None] | None:
    """Decode one binary numeric variable from an absolute payload span.

    The trailing resource index provides ``size`` for the payload, but the
    recovered descriptor also implies an expected width for known compact
    families. Reading the larger of the two keeps decoding tolerant of the
    one-byte reconciliation case handled by ``DatasetDescriptor`` while still
    honoring indexed resource lengths.
    """
    if not variable.is_binary_numeric:
        return None
    payload_size = size
    expected_size = variable.physical_size(dataset.row_count)
    if expected_size is not None:
        payload_size = max(payload_size, expected_size)
    return decode_compact_values_with_hints(
        data[start : start + payload_size],
        variable,
        dataset.row_count,
    )
