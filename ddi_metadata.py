"""Parser for DDI (Data Documentation Initiative) XML metadata files.

This module is test/support code rather than part of the NESSTAR container
parser itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

DDI_NS = "http://www.icpsr.umich.edu/DDI"
NS = {"ddi": DDI_NS}


@dataclass
class Category:
    value: str
    label: str
    frequency: int


@dataclass
class SummaryStats:
    valid_count: int = 0
    invalid_count: int = 0
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    stdev: float | None = None


@dataclass
class Variable:
    id: str
    name: str
    file_id: str
    width: int
    var_type: str
    interval: str
    decimals: int
    label: str
    categories: list[Category] = field(default_factory=list)
    stats: SummaryStats = field(default_factory=SummaryStats)


@dataclass
class FileDescription:
    id: str
    name: str
    record_count: int
    var_count: int
    file_type: str
    index: int
    variables: list[Variable] = field(default_factory=list)


@dataclass
class DatasetMetadata:
    title: str
    id: str
    files: dict[str, FileDescription] = field(default_factory=dict)


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_variable(var_el: ET.Element) -> Variable:
    variable_id = var_el.get("ID", "")
    name = var_el.get("name", "")
    file_id = var_el.get("files", "")
    interval = var_el.get("intrvl", "discrete")
    decimals = int(var_el.get("dcml", "0"))

    loc = var_el.find("ddi:location", NS)
    width = int(loc.get("width", "0")) if loc is not None else 0

    fmt = var_el.find("ddi:varFormat", NS)
    var_type = fmt.get("type", "character") if fmt is not None else "character"
    label = _text(var_el.find("ddi:labl", NS))

    stats = SummaryStats()
    for stat in var_el.findall("ddi:sumStat", NS):
        stat_type = stat.get("type", "")
        stat_value = _text(stat)
        if stat_type == "vald":
            stats.valid_count = int(stat_value)
        elif stat_type == "invd":
            stats.invalid_count = int(stat_value)
        elif stat_type == "min":
            stats.min = _float_or_none(stat_value)
        elif stat_type == "max":
            stats.max = _float_or_none(stat_value)
        elif stat_type == "mean":
            stats.mean = _float_or_none(stat_value)
        elif stat_type == "stdev":
            stats.stdev = _float_or_none(stat_value)

    categories: list[Category] = []
    for category in var_el.findall("ddi:catgry", NS):
        category_value = _text(category.find("ddi:catValu", NS))
        category_label = _text(category.find("ddi:labl", NS))
        category_stat = category.find("ddi:catStat", NS)
        frequency = int(_text(category_stat)) if category_stat is not None and _text(category_stat) else 0
        categories.append(Category(value=category_value, label=category_label, frequency=frequency))

    return Variable(
        id=variable_id,
        name=name,
        file_id=file_id,
        width=width,
        var_type=var_type,
        interval=interval,
        decimals=decimals,
        label=label,
        categories=categories,
        stats=stats,
    )


def _parse_file_index(uri: str) -> int:
    normalized = uri.replace("&amp;", "&")
    for part in normalized.replace("?", "&").split("&"):
        if part.startswith("Index="):
            return int(part.split("=", 1)[1])
    return 0


def parse_ddi_xml(path: str | Path) -> DatasetMetadata:
    tree = ET.parse(path)
    root = tree.getroot()

    title = _text(root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:titl", NS))
    document_id = root.get("ID", "")
    metadata = DatasetMetadata(title=title, id=document_id)

    for file_desc in root.findall("ddi:fileDscr", NS):
        file_id = file_desc.get("ID", "")
        uri = file_desc.get("URI", "")
        file_text = file_desc.find("ddi:fileTxt", NS)
        if file_text is None:
            continue

        file_name = _text(file_text.find("ddi:fileName", NS))
        dimensions = file_text.find("ddi:dimensns", NS)
        record_count = int(_text(dimensions.find("ddi:caseQnty", NS))) if dimensions is not None else 0
        var_count = int(_text(dimensions.find("ddi:varQnty", NS))) if dimensions is not None else 0
        file_type = _text(file_text.find("ddi:fileType", NS))

        metadata.files[file_id] = FileDescription(
            id=file_id,
            name=file_name,
            record_count=record_count,
            var_count=var_count,
            file_type=file_type,
            index=_parse_file_index(uri),
        )

    for variable in root.findall(".//ddi:dataDscr/ddi:var", NS):
        parsed = _parse_variable(variable)
        if parsed.file_id in metadata.files:
            metadata.files[parsed.file_id].variables.append(parsed)

    return metadata
