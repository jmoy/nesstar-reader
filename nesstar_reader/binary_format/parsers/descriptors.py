"""Parser for the dataset descriptor table."""

from __future__ import annotations

from ..constants import HEADER_BASE_RECORD_ID, HEADER_DATASET_COUNT, HEADER_DESCRIPTOR_RECORD_SIZE
from ..types import DatasetDescriptor, NesstarBinaryFormatError, TrailingResourceIndexRecord
from ..utils import u16le, u32le


def parse_descriptors(data: bytes, descriptor_table_offset: int) -> list[DatasetDescriptor]:
    """Parse the dataset descriptor table at the header-resolved offset."""
    count = data[HEADER_DATASET_COUNT]
    record_size = u16le(data, HEADER_DESCRIPTOR_RECORD_SIZE)
    if record_size < 26:
        raise NesstarBinaryFormatError(f"Descriptor record size {record_size} is too small")
    descriptors: list[DatasetDescriptor] = []
    offset = descriptor_table_offset
    for _ in range(count):
        row_count = u32le(data, offset + 8)
        row_count_copy = u32le(data, offset + 12)
        if row_count_copy != row_count:
            raise NesstarBinaryFormatError(
                f"Descriptor at {offset:#x} has row_count_copy {row_count_copy} != row_count {row_count}"
            )
        descriptors.append(
            DatasetDescriptor(
                dataset_number=u32le(data, offset),
                variable_count=u32le(data, offset + 4),
                row_count=row_count,
                file_description_record_id=u32le(data, offset + 16),
                variable_directory_entry_size=u16le(data, offset + 20),
                variable_directory_record_id=u32le(data, offset + 22),
            )
        )
        offset += record_size
    return descriptors


def discover_descriptor_section_offset(
    data: bytes,
    trailing_resource_index: dict[int, TrailingResourceIndexRecord],
) -> int:
    """Resolve the dataset descriptor table offset through the resource index."""
    base_id = u32le(data, HEADER_BASE_RECORD_ID)
    record = trailing_resource_index.get(base_id)
    if record is None:
        raise NesstarBinaryFormatError(
            f"Resource index has no record for base_record_id {base_id}"
        )
    return record.target_offset
