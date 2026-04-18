"""Parser for per-dataset variable directory tables."""

from __future__ import annotations

from ..types import VariableDirectoryEntry
from ..utils import decode_directory_name, is_plausible_variable_name, u32le


def parse_directory_entry(entry: bytes) -> VariableDirectoryEntry:
    return VariableDirectoryEntry(
        entry_index=u32le(entry, 0),
        name=decode_directory_name(entry),
        width_value=entry[149],
        variable_id=u32le(entry, 15),
        label_resource_id=u32le(entry, 127),
        category_resource_id=int.from_bytes(entry[131:133], "little"),
        object_id=u32le(entry, 155),
        mode_code=entry[159],
        value_format_code=entry[5],
        value_offset_i64=int.from_bytes(entry[6:14], "little", signed=True),
    )


def validate_directory(
    data: bytes,
    offset: int,
    count: int,
    entry_size: int,
    *,
    expected_first_variable_id: int | None = None,
) -> list[VariableDirectoryEntry] | None:
    if offset < 0 or offset >= len(data):
        return None
    if entry_size < 160:
        return None

    entries: list[VariableDirectoryEntry] = []
    previous_entry_index: int | None = None
    previous_variable_id: int | None = None
    for index in range(count):
        start = offset + index * entry_size
        end = start + entry_size
        if end > len(data):
            return None
        parsed = parse_directory_entry(data[start:end])
        if previous_entry_index is not None and parsed.entry_index != previous_entry_index + 1:
            return None
        if expected_first_variable_id is not None and index == 0 and parsed.variable_id != expected_first_variable_id:
            return None
        if previous_variable_id is not None and parsed.variable_id != previous_variable_id + 1:
            return None
        if not is_plausible_variable_name(parsed.name):
            return None
        entries.append(parsed)
        previous_entry_index = parsed.entry_index
        previous_variable_id = parsed.variable_id
    return entries
