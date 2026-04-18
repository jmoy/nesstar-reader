from __future__ import annotations

from pathlib import Path

import pytest

from nesstar_reader.binary import (
    ParsedEmbeddedMetadata,
    ParsedNesstarBinary,
    parse_embedded_dataset_metadata,
    parse_nesstar_binary,
)
from ddi_metadata import DatasetMetadata, parse_ddi_xml


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--nesstar",
        action="store",
        required=True,
        help="Path to the .Nesstar file to validate.",
    )
    parser.addoption(
        "--xml",
        action="store",
        help="Optional path to the matching DDI XML file.",
    )


@pytest.fixture(scope="session")
def nesstar_path(pytestconfig: pytest.Config) -> Path:
    return Path(pytestconfig.getoption("nesstar")).resolve()


@pytest.fixture(scope="session")
def xml_path(pytestconfig: pytest.Config) -> Path | None:
    value = pytestconfig.getoption("xml")
    if value is None:
        return None
    return Path(value).resolve()


@pytest.fixture(scope="session")
def parsed_binary(nesstar_path: Path) -> ParsedNesstarBinary:
    return parse_nesstar_binary(nesstar_path)


@pytest.fixture(scope="session")
def parsed_metadata(xml_path: Path | None) -> DatasetMetadata | None:
    if xml_path is None:
        return None
    return parse_ddi_xml(xml_path)


@pytest.fixture(scope="session")
def embedded_metadata(nesstar_path: Path) -> ParsedEmbeddedMetadata:
    return parse_embedded_dataset_metadata(nesstar_path)


@pytest.fixture(scope="session")
def nesstar_bytes(nesstar_path: Path) -> bytes:
    return nesstar_path.read_bytes()
