"""Text-resource decoders for label payloads and other trailing text blocks."""

from __future__ import annotations

from ..types import TrailingResourceIndexRecord


def decode_text_resource(
    data: bytes,
    trailing_resource_index: dict[int, TrailingResourceIndexRecord],
    record_id: int,
) -> str:
    if record_id == 0:
        return ""
    record = trailing_resource_index.get(record_id)
    if record is None:
        return ""
    raw = data[record.target_offset : record.target_offset + record.length]
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return raw.decode("latin1", errors="replace").strip()
