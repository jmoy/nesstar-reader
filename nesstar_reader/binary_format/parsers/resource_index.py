"""Parser for the trailing resource index table."""

from __future__ import annotations

from ..constants import HEADER_RESOURCE_INDEX_OFFSET, TRAILING_RESOURCE_INDEX_RECORD_SIZE
from ..types import NesstarBinaryFormatError, TrailingResourceIndexRecord
from ..utils import u32le


def parse_trailing_resource_index(data: bytes) -> dict[int, TrailingResourceIndexRecord]:
    offset = u32le(data, HEADER_RESOURCE_INDEX_OFFSET)
    records_offset = offset + 4
    if records_offset + TRAILING_RESOURCE_INDEX_RECORD_SIZE > len(data):
        raise NesstarBinaryFormatError("Trailing resource index is truncated")

    record_count = u32le(data, offset)
    end = records_offset + record_count * TRAILING_RESOURCE_INDEX_RECORD_SIZE
    if end > len(data):
        raise NesstarBinaryFormatError("Trailing resource index extends beyond end of file")

    records: dict[int, TrailingResourceIndexRecord] = {}
    cursor = records_offset
    for _ in range(record_count):
        length = u32le(data, cursor + 10)
        record = TrailingResourceIndexRecord(
            record_id=u32le(data, cursor),
            target_offset=u32le(data, cursor + 4),
            length=length,
        )
        records[record.record_id] = record
        cursor += TRAILING_RESOURCE_INDEX_RECORD_SIZE
    return records
