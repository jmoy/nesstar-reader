"""Top-level NESSTAR layout parser that stitches table parsers together."""

from __future__ import annotations

from pathlib import Path

from .constants import HEADER_DATASET_COUNT, MAGIC
from .parsers.descriptors import discover_descriptor_section_offset, parse_descriptors
from .parsers.directory import validate_directory
from .parsers.resource_index import parse_trailing_resource_index
from .types import DatasetDescriptor, NesstarBinaryFormatError, ParsedNesstarBinary
from .utils import u32le


def discover_trailing_metadata_bounds(
    data: bytes,
    datasets: list[DatasetDescriptor],
) -> tuple[int | None, int | None]:
    start_offset: int | None = None
    if datasets:
        last = datasets[-1]
        if last.directory_offset is not None:
            start_offset = last.directory_offset + last.variable_count * last.variable_directory_entry_size

    end_offset = u32le(data, 0x25)
    if start_offset is not None and start_offset > end_offset:
        start_offset = end_offset
    return start_offset, end_offset


def parse_nesstar_binary(path: str | Path) -> ParsedNesstarBinary:
    file_path = Path(path)
    data = file_path.read_bytes()

    if data[:8] != MAGIC:
        raise NesstarBinaryFormatError("Missing NESSTART magic header")

    trailing_resource_index = parse_trailing_resource_index(data)
    descriptor_table_offset = discover_descriptor_section_offset(data, trailing_resource_index)
    descriptors = parse_descriptors(data, descriptor_table_offset)

    for descriptor in descriptors:
        first_variable_id = descriptor.variable_directory_record_id + 1
        base_var_record = trailing_resource_index.get(descriptor.variable_directory_record_id)
        if base_var_record is None:
            raise NesstarBinaryFormatError(
                f"Resource index has no record for variable_directory_record_id {descriptor.variable_directory_record_id}"
            )
        directory_offset = base_var_record.target_offset

        parsed_entries = validate_directory(
            data,
            directory_offset,
            descriptor.variable_count,
            descriptor.variable_directory_entry_size,
            expected_first_variable_id=first_variable_id,
        )
        if parsed_entries is None:
            raise NesstarBinaryFormatError(f"Directory at {directory_offset:#x} failed validation")

        first_var_record = trailing_resource_index.get(first_variable_id)
        if first_var_record is None:
            raise NesstarBinaryFormatError(
                f"Resource index has no record for first variable id {first_variable_id}"
            )
        data_start = first_var_record.target_offset

        descriptor.directory_offset = directory_offset
        descriptor.data_start_offset = data_start
        descriptor.variables = parsed_entries
        descriptor.indexed_variable_offsets = {
            variable.variable_id: trailing_resource_index[variable.variable_id].target_offset
            for variable in parsed_entries
            if variable.variable_id in trailing_resource_index
        }
        descriptor.indexed_variable_lengths = {
            variable.variable_id: trailing_resource_index[variable.variable_id].length
            for variable in parsed_entries
            if variable.variable_id in trailing_resource_index
        }
        assert len(descriptor.indexed_variable_offsets) == len(parsed_entries), (
            f"Missing indexed variable offsets for dataset {descriptor.dataset_number}"
        )
        assert len(descriptor.indexed_variable_lengths) == len(parsed_entries), (
            f"Missing indexed variable lengths for dataset {descriptor.dataset_number}"
        )

        if parsed_entries:
            last_variable_id = parsed_entries[-1].variable_id
            last_start = descriptor.indexed_variable_offsets[last_variable_id]
            last_length = descriptor.indexed_variable_lengths[last_variable_id]
            descriptor.data_end_offset = last_start + last_length - 1
            assert descriptor.data_end_offset == directory_offset - 1, (
                f"Dataset {descriptor.dataset_number} indexed payload end {descriptor.data_end_offset:#x} "
                f"does not match directory boundary {directory_offset - 1:#x}"
            )
        else:
            descriptor.data_end_offset = data_start - 1

    trailing_metadata_start_offset, trailing_metadata_end_offset = discover_trailing_metadata_bounds(data, descriptors)

    return ParsedNesstarBinary(
        path=file_path,
        file_size=u32le(data, 0x0B),
        version_bytes=data[0x08:0x0B],
        dataset_count_hint=data[HEADER_DATASET_COUNT],
        datasets=descriptors,
        trailing_metadata_start_offset=trailing_metadata_start_offset,
        trailing_metadata_end_offset=trailing_metadata_end_offset,
        trailing_resource_index=trailing_resource_index,
    )
