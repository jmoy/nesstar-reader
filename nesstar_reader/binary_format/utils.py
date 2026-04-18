"""Small parsing helpers used across the parser tree."""

from __future__ import annotations

from .constants import NAME_OFFSET_IN_ENTRY, NAME_UTF16LE_BYTES


def u16le(data: bytes, offset: int) -> int:
    """Read an unsigned 16-bit little-endian integer from ``data``."""
    return int.from_bytes(data[offset : offset + 2], "little")


def u32le(data: bytes, offset: int) -> int:
    """Read an unsigned 32-bit little-endian integer from ``data``."""
    return int.from_bytes(data[offset : offset + 4], "little")


def decode_directory_name(entry: bytes) -> str:
    """Decode the fixed UTF-16LE variable-name field from a directory entry."""
    raw = entry[NAME_OFFSET_IN_ENTRY : NAME_OFFSET_IN_ENTRY + NAME_UTF16LE_BYTES]
    return raw.decode("utf-16le", errors="ignore").split("\x00", 1)[0]


def is_plausible_variable_name(name: str) -> bool:
    """Return whether a decoded directory name looks like a variable id."""
    if not name or len(name) > 40:
        return False
    if not (name[0].isalpha() or name[0] == "_"):
        return False
    return all(ch.isalnum() or ch == "_" for ch in name)
