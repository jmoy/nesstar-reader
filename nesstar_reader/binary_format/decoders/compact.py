"""Column-value decoders derived from compact storage descriptors."""

from __future__ import annotations

import struct

from ..types import DatasetDescriptor, VariableDirectoryEntry


def unpack_packed_nibbles(data: bytes, record_count: int) -> list[int]:
    values: list[int] = []
    for byte in data[: (record_count + 1) // 2]:
        values.append((byte >> 4) & 0x0F)
        values.append(byte & 0x0F)
    return values[:record_count]


def _decode_uint16_values(data: bytes, record_count: int) -> list[int]:
    return [int.from_bytes(data[i : i + 2], "little") for i in range(0, min(len(data), record_count * 2), 2)]


def _decode_uint24_values(data: bytes, record_count: int) -> list[int]:
    return [int.from_bytes(data[i : i + 3], "little") for i in range(0, min(len(data), record_count * 3), 3)]


def _decode_uint32_values(data: bytes, record_count: int) -> list[int]:
    return [int.from_bytes(data[i : i + 4], "little") for i in range(0, min(len(data), record_count * 4), 4)]


def _decode_uint40_values(data: bytes, record_count: int) -> list[int]:
    return [int.from_bytes(data[i : i + 5], "little") for i in range(0, min(len(data), record_count * 5), 5)]


def _decode_float64_values(data: bytes, record_count: int) -> list[float]:
    return [
        struct.unpack("<d", data[i : i + 8])[0]
        for i in range(0, min(len(data), record_count * 8), 8)
    ]


def decode_compact_values_hint(
    data: bytes,
    variable: VariableDirectoryEntry,
    record_count: int,
) -> list[int | float] | None:
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
    missing_value_code = variable.missing_value_code
    if missing_value_code is None:
        return values
    return [None if value == missing_value_code else value for value in values]


def apply_value_bias_hint(values: list[int], variable: VariableDirectoryEntry) -> list[int]:
    additive_offset = variable.additive_offset
    if additive_offset is None:
        return values
    return [value + additive_offset for value in values]


def decode_compact_values_with_hints(
    data: bytes,
    variable: VariableDirectoryEntry,
    record_count: int,
) -> list[int | float | None] | None:
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
