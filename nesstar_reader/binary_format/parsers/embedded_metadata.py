"""Parsers for embedded XML blocks, templates, and resolved metadata views."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ..constants import (
    HEADER_METADATA_BLOCK_1_RECORD_ID,
    HEADER_METADATA_BLOCK_2_RECORD_ID,
    HEADER_TEMPLATE_MANIFEST_ID,
)
from ..decoders.huffman import decode_embedded_metadata_block
from ..decoders.text import decode_text_resource
from ..types import (
    DatasetEmbeddedMetadata,
    EmbeddedCategory,
    EmbeddedMetadataBlock,
    EmbeddedStatOptions,
    EmbeddedTemplateDocument,
    EmbeddedTemplateReference,
    NesstarBinaryFormatError,
    ParsedEmbeddedMetadata,
    VariableEmbeddedMetadata,
)
from ..utils import u32le
from .resource_index import parse_trailing_resource_index


def xml_root(block: EmbeddedMetadataBlock) -> ET.Element:
    return ET.fromstring(block.decoded_xml)


def xml_bool(value: str | None) -> bool:
    return (value or "").upper() == "TRUE"


def parse_embedded_categories(block: EmbeddedMetadataBlock) -> list[EmbeddedCategory]:
    root = xml_root(block)
    if root.tag != "Categories":
        raise NesstarBinaryFormatError(f"Expected <Categories> block at {block.offset:#x}")
    return [
        EmbeddedCategory(value=child.get("Value", ""), label=child.get("Label", ""))
        for child in root.findall("Category")
    ]


def parse_embedded_stat_options(block: EmbeddedMetadataBlock) -> EmbeddedStatOptions:
    root = xml_root(block)
    if root.tag != "ExtVarInf":
        raise NesstarBinaryFormatError(f"Expected <ExtVarInf> block at {block.offset:#x}")
    stat_options = root.find("StatOptions")
    if stat_options is None:
        raise NesstarBinaryFormatError(f"Missing <StatOptions> in ExtVarInf block at {block.offset:#x}")
    return EmbeddedStatOptions(
        min_enabled=xml_bool(stat_options.get("Min")),
        max_enabled=xml_bool(stat_options.get("Max")),
        mean_enabled=xml_bool(stat_options.get("Mean")),
        stddev_enabled=xml_bool(stat_options.get("StdDev")),
        mean_weighted_enabled=xml_bool(stat_options.get("MeanWeighted")),
        stddev_weighted_enabled=xml_bool(stat_options.get("StdDevWeighted")),
    )


def parse_embedded_file_description_name(block: EmbeddedMetadataBlock) -> str:
    root = xml_root(block)
    if root.tag != "FileDesc":
        raise NesstarBinaryFormatError(f"Expected <FileDesc> block at {block.offset:#x}")
    file_name = root.findtext("FileName")
    if file_name is None:
        raise NesstarBinaryFormatError(f"Missing <FileName> in FileDesc block at {block.offset:#x}")
    return file_name.strip()


def parse_embedded_title_and_id(block: EmbeddedMetadataBlock) -> tuple[str, str]:
    root = xml_root(block)
    title_stmt = root.find("./Citation/TitleStmt")
    if title_stmt is None:
        raise NesstarBinaryFormatError(f"Missing <TitleStmt> in embedded block at {block.offset:#x}")
    return (title_stmt.get("Title") or "").strip(), (title_stmt.get("IDNo") or "").strip()


def parse_embedded_template_manifest(data: bytes, offset: int, length: int) -> list[EmbeddedTemplateReference]:
    if length < 2:
        raise NesstarBinaryFormatError(f"Template manifest at {offset:#x} is truncated")
    count = int.from_bytes(data[offset : offset + 2], "little")
    entry_size = 76
    cursor = offset + 2
    expected_end = cursor + count * entry_size
    if expected_end > offset + length:
        raise NesstarBinaryFormatError(f"Template manifest at {offset:#x} exceeds its indexed length")

    result: list[EmbeddedTemplateReference] = []
    for _ in range(count):
        name_bytes = data[cursor : cursor + 72]
        record_id = int.from_bytes(data[cursor + 72 : cursor + 76], "little")
        cursor += entry_size
        name = name_bytes.split(b"\x00", 1)[0].decode("latin1", errors="replace")
        result.append(EmbeddedTemplateReference(name=name, record_id=record_id))
    return result


def parse_plain_xml_template_documents(
    data: bytes,
    manifest: list[EmbeddedTemplateReference],
    trailing_resource_index: dict[int, object],
) -> list[EmbeddedTemplateDocument]:
    documents: list[EmbeddedTemplateDocument] = []
    for entry in manifest:
        record = trailing_resource_index.get(entry.record_id)
        if record is None:
            continue
        start = record.target_offset
        end = start + record.length
        xml_text = data[start:end].decode("utf-8", errors="replace").rstrip()
        root = ET.fromstring(xml_text)
        template = root.find("Template")
        documents.append(
            EmbeddedTemplateDocument(
                record_id=entry.record_id,
                name=entry.name,
                root_tag=root.tag,
                version=root.get("Version", ""),
                author=(template.get("Author", "") if template is not None else ""),
                organization=(template.get("Organization", "") if template is not None else ""),
                xml_text=xml_text,
                tab_names=[tab.get("Name", "") for tab in root.findall(".//Tab")],
            )
        )
    return documents


def decode_header_metadata_blocks(path: str | Path) -> list[EmbeddedMetadataBlock]:
    data = Path(path).read_bytes()
    resource_index = parse_trailing_resource_index(data)
    rec1 = resource_index.get(HEADER_METADATA_BLOCK_1_RECORD_ID)
    rec2 = resource_index.get(HEADER_METADATA_BLOCK_2_RECORD_ID)
    if rec1 is None or rec2 is None:
        raise NesstarBinaryFormatError("Resource index missing header metadata block records (1, 2)")
    return [
        decode_embedded_metadata_block(data, rec1.target_offset - 1, has_dataset_index=True),
        decode_embedded_metadata_block(data, rec2.target_offset - 1, has_dataset_index=True),
    ]


def scan_trailing_metadata_blocks(
    path: str | Path,
    *,
    start_offset: int | None = None,
    end_offset: int | None = None,
) -> list[EmbeddedMetadataBlock]:
    from ..layout import parse_nesstar_binary

    parsed = parse_nesstar_binary(path)
    data = parsed.path.read_bytes()
    if start_offset is None:
        start_offset = parsed.trailing_metadata_start_offset or 0
    if end_offset is None:
        end_offset = parsed.trailing_metadata_end_offset or len(data)
    found: list[EmbeddedMetadataBlock] = []
    offset = start_offset
    while offset < end_offset:
        try:
            block = decode_embedded_metadata_block(data, offset)
        except NesstarBinaryFormatError:
            offset += 1
            continue
        if not block.decoded_xml.startswith("<?xml version='1.0'?>"):
            offset += 1
            continue
        label_end = offset
        label_start = label_end
        while label_start > start_offset and 32 <= data[label_start - 1] < 127:
            label_start -= 1
        block.ascii_prefix = data[label_start:label_end].decode("latin1", errors="ignore")
        found.append(block)
        offset = block.payload_offset + block.payload_length
    return found


def decode_indexed_metadata_block(
    data: bytes,
    trailing_resource_index: dict[int, object],
    record_id: int,
) -> EmbeddedMetadataBlock | None:
    record = trailing_resource_index.get(record_id)
    if record is None:
        return None
    try:
        block = decode_embedded_metadata_block(data, record.target_offset)
    except NesstarBinaryFormatError:
        return None
    if not block.decoded_xml.startswith("<?xml version='1.0'?>"):
        return None
    return block


def parse_embedded_dataset_metadata(path: str | Path) -> ParsedEmbeddedMetadata:
    from ..layout import parse_nesstar_binary

    parsed = parse_nesstar_binary(path)
    data = parsed.path.read_bytes()
    header_blocks = decode_header_metadata_blocks(path)
    template_manifest_id = u32le(data, HEADER_TEMPLATE_MANIFEST_ID)
    template_manifest_record = parsed.trailing_resource_index.get(template_manifest_id)
    template_manifest = (
        parse_embedded_template_manifest(data, template_manifest_record.target_offset, template_manifest_record.length)
        if template_manifest_record is not None
        else []
    )
    template_documents = parse_plain_xml_template_documents(
        data,
        template_manifest,
        parsed.trailing_resource_index,
    )

    datasets: list[DatasetEmbeddedMetadata] = []
    title = ""
    document_id = ""
    doc_description_block: EmbeddedMetadataBlock | None = None
    study_description_block: EmbeddedMetadataBlock | None = None

    for block in header_blocks:
        if block.xml_root_tag == "DocDesc":
            doc_description_block = block
        elif block.xml_root_tag == "StudyDesc":
            study_description_block = block
        block_title, block_document_id = parse_embedded_title_and_id(block)
        if block_title and not title:
            title = block_title
        if block_document_id and not document_id:
            document_id = block_document_id

    for descriptor in parsed.datasets:
        file_desc_block = decode_indexed_metadata_block(
            data,
            parsed.trailing_resource_index,
            descriptor.file_description_record_id,
        )
        if file_desc_block is None or file_desc_block.xml_root_tag != "FileDesc":
            raise NesstarBinaryFormatError(
                f"Could not resolve FileDesc block for dataset {descriptor.dataset_number} from record {descriptor.file_description_record_id}"
            )
        dataset_metadata = DatasetEmbeddedMetadata(
            dataset_number=descriptor.dataset_number,
            file_description_block=file_desc_block,
            file_name=parse_embedded_file_description_name(file_desc_block),
            record_count=descriptor.row_count,
            var_count=descriptor.variable_count,
        )
        for variable in descriptor.variables:
            variable_metadata = VariableEmbeddedMetadata(
                variable_name=variable.name,
                variable_id=variable.variable_id,
                label=decode_text_resource(data, parsed.trailing_resource_index, variable.label_resource_id),
                width_value=variable.width_value,
                object_id=variable.object_id,
                label_resource_id=variable.label_resource_id,
                category_resource_id=variable.category_resource_id,
            )
            if variable.object_id != 0:
                variable_metadata.ext_var_inf_block = decode_indexed_metadata_block(
                    data,
                    parsed.trailing_resource_index,
                    variable.object_id,
                )
            if variable_metadata.ext_var_inf_block is not None:
                variable_metadata.stat_options = parse_embedded_stat_options(variable_metadata.ext_var_inf_block)
            if variable.category_resource_id != 0:
                variable_metadata.categories_block = decode_indexed_metadata_block(
                    data,
                    parsed.trailing_resource_index,
                    variable.category_resource_id,
                )
            if variable_metadata.categories_block is not None:
                variable_metadata.categories = parse_embedded_categories(variable_metadata.categories_block)
            dataset_metadata.variables.append(variable_metadata)
        datasets.append(dataset_metadata)

    return ParsedEmbeddedMetadata(
        title=title,
        document_id=document_id,
        doc_description_block=doc_description_block,
        study_description_block=study_description_block,
        template_manifest=template_manifest,
        template_documents=template_documents,
        datasets=datasets,
    )
