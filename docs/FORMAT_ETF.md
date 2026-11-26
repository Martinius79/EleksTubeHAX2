# ETF – EleksTube Face format, version 1.0

`.etf` is the container for one clock face: a set of glyphs (digits 0–9 plus optional extra
glyphs) for one display size. It is written by `tools/etf` (Python) and the web UI (JS) and read
by the firmware component `components/etf`. Decisions: D-006, D-020.

Design goals: decode row by row into a small caller buffer (no full frame in RAM), lossless by
default, small on flash, robust against corrupt or truncated files, simple to implement in C,
Python and JavaScript.

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119.

## 1. Conventions

- All integer fields in headers and tables are **little-endian**.
- Offsets are absolute byte offsets from the start of the file.
- **Pixel data is RGB565 big-endian** (high byte first), i.e. exactly the byte order sent to the
  ST7789/ST7735 panels. Decoded rows can be passed to the display without conversion.
  This applies to all pixel streams and palette entries (section 5). Colour values inside the
  glyph table (`bg_color`, `key_color`) are ordinary little-endian `u16` numbers.
- RGB565: bits 15–11 red, 10–5 green, 4–0 blue.
- CRC32 is the IEEE 802.3 / zlib CRC (`crc32("123456789") = 0xCBF43926`).
- Text is UTF-8 without BOM.

## 2. File layout

```
+---------------------------+  0
| File header (32 bytes)    |
+---------------------------+  glyph_table_offset (4-byte aligned)
| Glyph table               |  glyph_count × 32 bytes, sorted by code
+---------------------------+  meta_offset (optional)
| Metadata (UTF-8 text)     |
+---------------------------+  data_offset of each glyph (4-byte aligned)
| Glyph data …              |
+---------------------------+
```

Sections MAY appear in a different order; readers MUST use the offsets. Gaps are allowed and
SHOULD be zero-filled. Sections MUST NOT overlap. Writers SHOULD NOT pad after the last
section, so that a truncated file is always detected.

## 3. File header (32 bytes)

| Off | Type | Field | Value / meaning |
|----:|------|-------|-----------------|
| 0 | u8[4] | `magic` | `"ETF"` followed by `0x1A` (`45 54 46 1A`) |
| 4 | u8 | `version_major` | `1` – readers MUST reject other major versions |
| 5 | u8 | `version_minor` | `0` – readers MUST accept higher minor versions (ignore unknown fields/flags marked reserved) |
| 6 | u16 | `header_size` | `32`; readers MUST use it to locate the end of the header and MUST reject values < 32 |
| 8 | u16 | `canvas_w` | display width in pixels (e.g. 135, 80), 1…1024 |
| 10 | u16 | `canvas_h` | display height in pixels (e.g. 240, 160), 1…1024 |
| 12 | u16 | `glyph_count` | 1…256 |
| 14 | u16 | `flags` | reserved, writers MUST write 0, readers MUST ignore |
| 16 | u32 | `glyph_table_offset` | multiple of 4 |
| 20 | u32 | `meta_offset` | 0 = no metadata |
| 24 | u32 | `meta_size` | 0…4096 bytes |
| 28 | u32 | `header_crc` | CRC32 over header bytes 0…27, then the glyph table, then the metadata (one running CRC) – protects all structural data |

## 4. Glyph table

`glyph_count` entries of 32 bytes, **sorted by `code` ascending, no duplicates** (allows binary
search).

| Off | Type | Field | Meaning |
|----:|------|-------|---------|
| 0 | u32 | `code` | glyph identifier = Unicode code point (see 4.1) |
| 4 | u16 | `x` | left edge of the glyph rectangle on the canvas |
| 6 | u16 | `y` | top edge |
| 8 | u16 | `w` | width, ≥ 1, `x + w ≤ canvas_w` |
| 10 | u16 | `h` | height, ≥ 1, `y + h ≤ canvas_h` |
| 12 | u8 | `encoding` | see section 5 |
| 13 | u8 | `flags` | bit 0 `HAS_KEY`: pixels equal to `key_color` are transparent; other bits reserved (0) |
| 14 | u16 | `key_color` | transparent colour (RGB565 value) if `HAS_KEY` |
| 16 | u16 | `bg_color` | fill colour (RGB565 value) for the canvas area outside the glyph rectangle |
| 18 | u16 | `reserved` | 0 |
| 20 | u32 | `data_offset` | start of the glyph data, multiple of 4 |
| 24 | u32 | `data_size` | size of the glyph data in bytes |
| 28 | u32 | `data_crc` | CRC32 over the glyph data |

The glyph rectangle allows encoders to crop uniform borders: the area outside it is filled with
`bg_color`. A glyph covering the full canvas has `x = y = 0`, `w = canvas_w`, `h = canvas_h`.

### 4.1 Glyph codes

| Code | Glyph | Required |
|------|-------|----------|
| U+0030…U+0039 | digits `0`…`9` | **yes** – a valid face MUST contain all ten |
| U+0020 | blank (digit off) | no – firmware falls back to `bg_color` of `0` |
| U+003A | `:` colon | no |
| U+002D | `-` | no |
| U+002E | `.` | no |
| U+E000 | `AM` indicator | no |
| U+E001 | `PM` indicator | no |
| U+E100…U+E1FF | status icons (WiFi, alarm, …), assigned in `docs/FORMAT_ETF.md` when used | no |

Other code points MAY be stored (e.g. letters for menus) and are ignored by firmware that does
not need them.

## 5. Encodings

Every encoding produces the glyph's `w × h` pixels **row by row, top to bottom, left to right**.
Readers MUST reject unknown encoding values.

| Value | Name | Lossless | Typical use |
|------:|------|----------|-------------|
| 0 | `RAW565` | yes | tiny glyphs, debugging |
| 1 | `RLE565` | yes | flat graphics with large single-colour areas |
| 2 | `PAL8_RLE` | yes if ≤ 256 colours | flat graphics with few colours |
| 3 | `DEFLATE565` | yes | photo-like faces (glow, gradients, textures) |
| 4 | `DEFLATE_PAL8` | yes if ≤ 256 colours | photo-like faces after optional quantisation |
| 5–255 | reserved | | (QOI was considered and is not needed, see D-020) |

### 5.1 `RAW565` (0)

`w × h` pixels, 2 bytes each (big-endian). `data_size = 2·w·h`.

### 5.2 `RLE565` (1)

A sequence of packets. Each packet starts with a control byte `c`:

- `c & 0x80` set → **run**: one pixel (2 bytes) follows, repeated `(c & 0x7F) + 1` times (1…128).
- `c & 0x80` clear → **literal**: `c + 1` pixels (1…128) follow, 2 bytes each.

Packets MUST NOT cross row boundaries (every row starts with a new packet), so a decoder can stop
exactly at the end of a row. The data MUST end exactly after the last pixel of the last row.

### 5.3 `PAL8_RLE` (2)

```
u16  palette_count      1…256 (little-endian)
u8   palette[count][2]  RGB565 big-endian
...  packets            as RLE565, but every pixel is 1 byte: a palette index
```

Indices MUST be `< palette_count`.

### 5.4 `DEFLATE565` (3)

A **raw DEFLATE stream** (RFC 1951, no zlib/gzip header) of the `RAW565` pixel bytes.
The encoder MUST NOT use match distances above **4096 bytes** (zlib `wbits = 12`), so decoders
can use a 4 KB ring buffer. The decompressed size MUST be exactly `2·w·h`.

Firmware uses the ROM `tinfl` inflater (miniz, present on ESP32, -S2, -S3, -C3) with a 4 KB
wrapping dictionary; RAM during decode ≈ 4 KB window + ~11 KB decompressor state.

### 5.5 `DEFLATE_PAL8` (4)

```
u16  palette_count      1…256 (little-endian)
u8   palette[count][2]  RGB565 big-endian
...  raw DEFLATE stream of w·h palette indices (1 byte each), max distance 4096
```

## 6. Metadata

Optional UTF-8 text, `key=value` lines separated by `\n`, at most 4096 bytes. Unknown keys MUST
be ignored. Defined keys:

| Key | Example |
|-----|---------|
| `name` | `Nixie Glow` |
| `author` | `EleksTubeHAX2 facegen` |
| `license` | `CC0-1.0` (SPDX identifier) |
| `generator` | `facegen nixie 0.1` |
| `description` | free text |
| `url` | source or catalogue page |

## 7. Validation (readers)

Readers MUST check before using a file, and reject it otherwise:

1. `magic`, `version_major`, `header_size`; table and metadata inside the file; `header_crc`.
2. `canvas_w`, `canvas_h`, `glyph_count` within the ranges above.
3. Glyph table inside the file, 4-byte aligned, codes strictly ascending, all ten digits present.
4. For every glyph: rectangle inside the canvas, `encoding` known, `data_offset + data_size`
   inside the file, no overlap with header/table/metadata.
5. While decoding: no read beyond `data_size`, runs never exceed the row, palette indices in
   range, DEFLATE output exactly the expected size. A decoding error MUST be reported, never
   produce out-of-bounds writes.

`data_crc` SHOULD be verified when a file is stored (upload, OTA of built-in faces) and MAY be
verified at boot. Checking it on every redraw is not required.

## 8. Decoder model (informative)

```c
etf_face_t face;                                     // parsed header + glyph table
etf_open(&face, &reader);                            // reader = read(offset, buf, len) callback
const etf_glyph_t *g = etf_find(&face, '7');
etf_dec_t dec;                                       // per-glyph streaming state
etf_dec_begin(&dec, &face, g, work_buf, work_size);  // work buffer only for DEFLATE (~15 KB)
for (int y = 0; y < g->h; y++) {
    etf_dec_row(&dec, row_buf);                      // w pixels, big-endian RGB565
    /* send row (or batch of rows) to the panel at (g->x, g->y + y) */
}
etf_dec_end(&dec);
```

## 9. File naming and sizes

One file per face and display size, e.g. `nixie-glow_135x240.etf`, `nixie-glow_80x160.etf`.
The encoder chooses the smallest lossless encoding per glyph; lossy palette quantisation is
only applied when explicitly requested.

Measured for the generated nixie face (135×240, 10 digits, see roadmap progress log):
RAW565 633 KB, RLE565 525 KB, PAL8_RLE 303 KB (lossy, 256 colours), **DEFLATE565 240 KB
(lossless)**, DEFLATE_PAL8 220 KB (lossy).

## 10. Versioning

- New optional fields, flags or glyph codes → minor version increase; old readers keep working.
- New encodings → minor version increase; old readers reject only glyphs using them.
- Incompatible layout changes → major version increase.
