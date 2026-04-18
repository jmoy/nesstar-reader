"""Static Huffman decoder for embedded XML metadata blocks."""

from __future__ import annotations

from dataclasses import dataclass
import heapq

from ..types import EmbeddedMetadataBlock, NesstarBinaryFormatError


@dataclass(slots=True)
class HuffmanNode:
    weight: int
    symbol: int | None = None
    left: "HuffmanNode | None" = None
    right: "HuffmanNode | None" = None


def build_static_huffman_codes(symbol_counts: list[tuple[int, int]]) -> dict[int, str]:
    if not symbol_counts:
        raise NesstarBinaryFormatError("Embedded metadata block has an empty symbol table")

    heap: list[tuple[int, int, HuffmanNode]] = []
    counter = 0
    for symbol, weight in sorted(symbol_counts, key=lambda item: (item[1], item[0])):
        heapq.heappush(heap, (weight, counter, HuffmanNode(weight=weight, symbol=symbol)))
        counter += 1

    while len(heap) > 1:
        left = heapq.heappop(heap)[2]
        right = heapq.heappop(heap)[2]
        node = HuffmanNode(weight=left.weight + right.weight, left=left, right=right)
        heapq.heappush(heap, (node.weight, counter, node))
        counter += 1

    root = heap[0][2]
    codes: dict[int, str] = {}

    def visit(node: HuffmanNode, prefix: str = "") -> None:
        if node.symbol is not None:
            codes[node.symbol] = prefix or "0"
            return
        assert node.left is not None and node.right is not None
        visit(node.left, prefix + "0")
        visit(node.right, prefix + "1")

    visit(root)
    return codes


def decode_huffman_lsb_first(payload: bytes, codes: dict[int, str], output_length: int) -> tuple[bytes, int]:
    reverse_codes = {bits: symbol for symbol, bits in codes.items()}
    decoded: list[int] = []
    current = ""
    used_bits = 0

    for bit_index in range(len(payload) * 8):
        byte = payload[bit_index // 8]
        bit = (byte >> (bit_index % 8)) & 1
        current += "1" if bit else "0"
        if current in reverse_codes:
            decoded.append(reverse_codes[current])
            current = ""
            if len(decoded) == output_length:
                used_bits = bit_index + 1
                break

    if len(decoded) != output_length:
        raise NesstarBinaryFormatError("Failed to fully decode embedded metadata block")

    return bytes(decoded), (used_bits + 7) // 8


def decode_embedded_metadata_block(data: bytes, offset: int, *, has_dataset_index: bool = False) -> EmbeddedMetadataBlock:
    cursor = offset
    dataset_index: int | None = None
    if has_dataset_index:
        dataset_index = data[cursor]
        cursor += 1

    symbol_count = data[cursor]
    if symbol_count <= 0:
        raise NesstarBinaryFormatError(f"Invalid metadata symbol count at {offset:#x}")
    cursor += 1
    cursor += 1

    symbol_counts: list[tuple[int, int]] = []
    previous_symbol = -1
    for _ in range(symbol_count):
        symbol = data[cursor]
        count = int.from_bytes(data[cursor + 1 : cursor + 5], "little")
        cursor += 5
        if symbol <= previous_symbol or count <= 0:
            raise NesstarBinaryFormatError(f"Invalid metadata symbol table at {offset:#x}")
        symbol_counts.append((symbol, count))
        previous_symbol = symbol

    output_length = int.from_bytes(data[cursor : cursor + 4], "little")
    cursor += 4

    if output_length != sum(count for _, count in symbol_counts):
        raise NesstarBinaryFormatError(f"Metadata length mismatch at {offset:#x}")

    codes = build_static_huffman_codes(symbol_counts)
    decoded_bytes, payload_length = decode_huffman_lsb_first(data[cursor:], codes, output_length)
    decoded_xml = decoded_bytes.decode("utf-8", errors="replace")

    return EmbeddedMetadataBlock(
        offset=offset,
        symbol_count=symbol_count,
        output_length=output_length,
        payload_offset=cursor,
        payload_length=payload_length,
        decoded_xml=decoded_xml,
        dataset_index=dataset_index,
    )

