# NESSTAR Format Notes

## Scope

This document describes the `.Nesstar` container format as recovered from these
files:

- `DDI-IND-CSO-PLFS-2022-23.Nesstar`
- `DDI-IND-CSO-PLFS-2023-23.Nesstar`
- `DDI-IND-CSO-PLFS-2023-24.Nesstar`
- `DDI-IND-MOSPI-NSSO-HCES22-23.Nesstar`

This is not an official NESSTAR specification.

## Data Types And Notation

Use these names:

- `u8`: 1-byte unsigned integer
- `u16le`: 2-byte little-endian unsigned integer
- `u32le`: 4-byte little-endian unsigned integer
- `i64le`: 8-byte little-endian signed integer
- `f64le`: 8-byte little-endian IEEE-754 double

All offsets are file offsets in bytes.

Byte ranges use inclusive indexes. Example: `0x25..0x28`.

## Overview

A `.Nesstar` file is a container for:

- dataset layout metadata
- dataset column data
- embedded XML metadata
- text resources
- template documents

Two directory structures locate most of the file:

- the header, which points to the dataset descriptor table and template manifest
- the trailing resource index, which maps record ids to payload offsets and
  lengths

The broad layout is:

```text
header
compressed metadata block 1
compressed metadata block 2
optional template-manifest data
dataset descriptor table
dataset 1 data region
dataset 1 variable directory
dataset 2 data region
dataset 2 variable directory
...
trailing resource area
trailing resource index count (`u32le`)
trailing resource index records
```

## Top-Level Structure

For the tested files:

1. `u32le(file, 0x25)` is the offset of the trailing resource index count.
2. The trailing resource index begins there with a `u32le` record count.
3. Header field `0x2F..0x32` is the record id of the dataset descriptor table.
4. Header field `0x4F..0x52` is the record id of the template manifest.
5. Each dataset descriptor gives the record id of its variable directory and
   the record id of its `FileDesc` block.
6. The first variable id in a dataset is `variable_directory_record_id + 1`.
7. Variable data resources are addressed directly by `variable_id` in the
   trailing resource index.

## Header

The tested files use these header fields:

| Offset | Type | Meaning |
|---|---|---|
| `0x00..0x07` | 8 bytes | ASCII `NESSTART` |
| `0x08..0x0A` | 3 bytes | version bytes |
| `0x0B..0x0E` | `u32le` | file size |
| `0x25..0x28` | `u32le` | offset of trailing resource index count |
| `0x2B` | `u8` | dataset count |
| `0x2D..0x2E` | `u16le` | dataset descriptor record size |
| `0x2F..0x32` | `u32le` | record id of the dataset descriptor table |
| `0x4F..0x52` | `u32le` | record id of the template manifest |

## Trailing Resource Index

The trailing resource index begins with a `u32le` record count followed by
15-byte records.

### Parsed fields

| Field name | Relative bytes | Type | Meaning |
|---|---|---|---|
| `record_id` | `0..3` | `u32le` | lookup key |
| `target_offset` | `4..7` | `u32le` | file offset of the resource payload |
| `length` | `10..13` | `u32le` | payload length |

### Record id usage

| Lookup key | Resolves to |
|---|---|
| `1` | compressed metadata block 1 |
| `2` | compressed metadata block 2 |
| header field `0x2F` | dataset descriptor table |
| header field `0x4F` | template manifest |
| `variable_directory_record_id` | dataset variable directory |
| `variable_id` | variable data resource |
| `file_description_record_id` | dataset `FileDesc` XML block |
| `label_resource_id` | variable label text resource |
| `category_resource_id` | variable `Categories` XML block |
| `object_id` | variable XML metadata block; in the tested files this is
  usually `ExtVarInf` |

## Dataset Descriptor Table

The dataset descriptor table is a contiguous array of records whose size is
`u16le(file, 0x2D)`.

### Fields

| Field name | Relative bytes | Type | Meaning |
|---|---|---|---|
| `dataset_number` | `0..3` | `u32le` | dataset number |
| `variable_count` | `4..7` | `u32le` | variable count |
| `row_count` | `8..11` | `u32le` | row count |
| `file_description_record_id` | `16..19` | `u32le` | dataset `FileDesc` record id |
| `variable_directory_entry_size` | `20..21` | `u16le` | size of one variable-directory entry |
| `variable_directory_record_id` | `22..25` | `u32le` | record id of the variable directory |

The `u32le` at `12..15` is equal to `row_count` in the tested files.

## Dataset Layout

Each dataset has:

- a data region
- a variable directory

For the tested files:

- `start(variable) = resource_index[variable_id].target_offset`
- `size(variable) = resource_index[variable_id].length`
- `data_start_offset = start(first_variable)`
- `data_end_offset = start(last_variable) + size(last_variable) - 1`

The variable directory begins at:

- `resource_index[variable_directory_record_id].target_offset`

The variable directory entry size is:

- `variable_directory_entry_size`

In the tested files, the end of the last variable payload is the byte
immediately before the variable directory.

## Variable Directory Entry

The variable directory is an array of entries of size
`variable_directory_entry_size`.

The currently used field set lies within the first 160 bytes.

### Fields

| Field name | Relative bytes | Type | Meaning |
|---|---|---|---|
| `entry_index` | `0..3` | `u32le` | consecutive entry number |
| `value_format_code` | `5` | `u8` | binary numeric format selector when `mode_code == 5` |
| `value_offset_i64` | `6..13` | `i64le` | additive offset for non-`f64le` binary numeric values |
| `variable_id` | `15..18` | `u32le` | record id of the variable data resource |
| `variable_name_text` | `63..126` | bytes | UTF-16LE variable name field |
| `label_resource_id` | `127..130` | `u32le` | record id of the variable label text resource |
| `category_resource_id` | `131..132` | `u16le` | record id of the variable `Categories` block |
| `width_value` | `149` | `u8` | maximum byte length of one `mode_code == 1` string slot |
| `object_id` | `155..158` | `u32le` | record id of per-variable XML metadata |
| `mode_code` | `159` | `u8` | top-level value-storage selector |

### Entry relationships

For the tested files:

- `entry_index` values are consecutive
- `variable_id` values are consecutive
- the first `variable_id` in a dataset is `variable_directory_record_id + 1`

### Variable name

`variable_name_text` is decoded as UTF-16LE, truncated at the first `NUL`.

For the tested files:

- the variable name terminates within `variable_name_text`
- bytes after the first name terminator are zero

## Column Data

`mode_code` selects the storage family.

Known values:

- `1` is NUL-terminated byte-string storage
- `5` is binary numeric storage

### NUL-terminated byte strings

When `mode_code == 1`:

- one row occupies a `width_value`-byte slot
- the slot stores a variable-width byte string terminated by `0x00`
- bytes after the first `0x00` are padding
- if the first byte is `0x00`, the stored string is empty

Column size is:

- `row_count * width_value`

### Binary numeric fields

When `mode_code == 5`, `value_format_code` selects the physical encoding.

#### `value_format_code`

Known values:

| `value_format_code` | Physical width | Meaning |
|---|---:|---|
| `2` | `1/2` byte per record | nibble-packed unsigned codes |
| `3` | `1` byte per record | byte-coded unsigned values |
| `4` | `2` bytes per record | `uint16` |
| `5` | `3` bytes per record | `uint24` |
| `6` | `4` bytes per record | `uint32` |
| `7` | `5` bytes per record | `uint40` |
| `10` | `8` bytes per record | `f64le` |

#### Missing-value codes

| Family | Raw missing value |
|---|---|
| nibble-packed unsigned codes | `0x0F` |
| byte-coded unsigned values | `0xFF` |
| `uint16` | `0xFFFF` |
| `uint24` | `0xFFFFFF` |
| `uint32` | `0xFFFFFFFF` |
| `uint40` | `0xFFFFFFFFFF` |
| `f64le` | `DBL_MAX` |

For non-`f64le` binary numeric values:

- if `value_offset_i64 == 0`, decoded value is the raw value
- otherwise, decoded value is `raw_value + value_offset_i64`

For `f64le`, `value_offset_i64` is not applied.

#### Nibble-packed unsigned codes

- physical size is `ceil(row_count / 2)` bytes
- even-numbered rows use the high nibble
- odd-numbered rows use the low nibble

#### Byte-coded unsigned values

- physical size is `row_count` bytes

#### `uint16`, `uint24`, `uint32`, `uint40`

| Family | Bytes per row |
|---|---:|
| `uint16` | `2` |
| `uint24` | `3` |
| `uint32` | `4` |
| `uint40` | `5` |

#### `f64le`

- physical size is `row_count * 8` bytes
- each row is one little-endian IEEE-754 double

## XML And Text Metadata

Three metadata payload types are present:

- compressed XML blocks
- text resources
- plain XML template documents

### Metadata resources

| Source of record id | Resource kind | Payload | Meaning |
|---|---|---|---|
| literal `1` | compressed XML | `DocDesc` | top-level document metadata |
| literal `2` | compressed XML | `StudyDesc` | top-level study metadata |
| `file_description_record_id` | compressed XML | `FileDesc` | dataset file name |
| `object_id` | compressed XML | usually `ExtVarInf` | per-variable metadata |
| `label_resource_id` | text resource | plain text | variable label |
| `category_resource_id` | compressed XML | `Categories` | categorical value labels |
| header field `0x4F` | binary manifest | template references | template lookup table |
| template manifest entry | plain XML | template document | template metadata |

### Compressed XML blocks

`DocDesc`, `StudyDesc`, `FileDesc`, `ExtVarInf`, and `Categories` use the same
static-Huffman XML container.

#### Block layout

| Relative bytes | Type | Meaning |
|---|---|---|
| optional `0` | `u8` | dataset-index byte, used by records `1` and `2` |
| next `0` | `u8` | symbol count |
| next `1` | `u8` | skipped byte |
| repeated | 5-byte entry | symbol-table entry |
| after table | `u32le` | decoded output length |
| remainder | bytes | Huffman payload |

Symbol-table entry layout:

| Relative bytes | Type | Meaning |
|---|---|---|
| `0` | `u8` | symbol byte |
| `1..4` | `u32le` | symbol frequency |

#### Huffman rules

- symbol values are strictly increasing across the symbol table
- frequencies are positive
- `output_length` is the sum of symbol frequencies
- bit order within each payload byte is least-significant-bit first
- left edge is `0`
- right edge is `1`
- the one-symbol case uses code `0`

For records `1` and `2`, decoding begins at `target_offset - 1`, and the
leading byte is a `dataset_index`.

For other XML resources, decoding begins at `target_offset`.

### XML values

Known XML payloads and fields:

- `DocDesc` and `StudyDesc`
  - `./Citation/TitleStmt` attributes `Title` and `IDNo`
- `FileDesc`
  - child text `FileName`
- `ExtVarInf`
  - `StatOptions` attributes `Min`, `Max`, `Mean`, `StdDev`,
    `MeanWeighted`, `StdDevWeighted`
- `Categories`
  - repeated `Category` attributes `Value` and `Label`

`FileDesc` is minimal in the tested files. Example:

```xml
<?xml version='1.0'?><FileDesc><FileName>hhv1</FileName></FileDesc>
```

### Text resources

Variable labels are text resources addressed by `label_resource_id`.

The text payload is:

1. read from `target_offset` for `length` bytes
2. decoded as UTF-8 if possible
3. otherwise decoded as Latin-1 with replacement
4. trimmed at both ends

### Template manifest

The template manifest is a binary table addressed by header field `0x4F`.

Manifest layout:

| Relative bytes | Type | Meaning |
|---|---|---|
| `0..1` | `u16le` | entry count |
| repeated | 76-byte entry | template entry |

Template entry layout:

| Relative bytes | Type | Meaning |
|---|---|---|
| `0..71` | bytes | template name, NUL-terminated |
| `72..75` | `u32le` | template record id |

Template documents are plain XML resources addressed by those template record
ids.

## Minimal Checklist

A matching implementation:

1. verifies header magic `NESSTART`
2. reads header fields `0x25`, `0x2B`, `0x2D`, `0x2F`, `0x4F`
3. parses the trailing resource index
4. parses the dataset descriptor table using the header-provided record size
5. parses each variable directory using the descriptor-provided entry size
6. resolves every variable start and size from the trailing resource index
7. decodes `mode_code == 1` fields as NUL-terminated byte strings stored in
   `width_value`-byte slots
8. decodes binary numeric fields from `mode_code`, `value_format_code`,
   `value_offset_i64`, and the raw missing-value codes
9. resolves XML blocks, text resources, and templates through the trailing
   resource index
