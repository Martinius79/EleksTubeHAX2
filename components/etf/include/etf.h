// SPDX-License-Identifier: GPL-3.0-or-later
// ETF clock-face decoder (docs/FORMAT_ETF.md v1.0).
//
// Usage:
//   etf_source_t src;  etf_source_from_memory(&src, data, size);   // or etf_source_from_file()
//   etf_face_t face;   etf_open(&face, &src);
//   const etf_glyph_t *g = etf_find(&face, '7');
//   void *work = malloc(etf_dec_work_size(g));                      // ~16 KB for DEFLATE glyphs
//   etf_dec_t dec;     etf_dec_begin(&dec, &face, g, work, etf_dec_work_size(g));
//   for (y = 0; y < g->h; y++) etf_dec_row(&dec, row);              // row: g->w * 2 bytes
//   etf_close(&face);
//
// Decoded pixels are RGB565 big-endian (panel byte order). Every function validates its input;
// corrupt files produce an error, never out-of-bounds memory access.

#pragma once

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ETF_VERSION_MAJOR 1
#define ETF_MAX_CANVAS    1024
#define ETF_MAX_GLYPHS    256
#define ETF_MAX_META      4096
#define ETF_DEFLATE_DICT  4096 // max DEFLATE match distance (spec 5.4)

#define ETF_CODE_BLANK 0x0020u
#define ETF_CODE_COLON 0x003Au
#define ETF_CODE_AM    0xE000u
#define ETF_CODE_PM    0xE001u

#define ETF_GLYPH_FLAG_HAS_KEY 0x01u

typedef enum {
    ETF_ENC_RAW565 = 0,
    ETF_ENC_RLE565 = 1,
    ETF_ENC_PAL8_RLE = 2,
    ETF_ENC_DEFLATE565 = 3,
    ETF_ENC_DEFLATE_PAL8 = 4,
} etf_encoding_t;

/** Reads exactly `len` bytes at `offset`; returns ESP_OK or an error. */
typedef esp_err_t (*etf_read_fn_t)(void *ctx, uint32_t offset, void *buf, size_t len);

typedef struct {
    etf_read_fn_t read;
    void *ctx;
    uint32_t size; // total file size in bytes
} etf_source_t;

typedef struct {
    uint32_t code; // Unicode code point
    uint16_t x, y, w, h;
    uint8_t encoding; // etf_encoding_t
    uint8_t flags;    // ETF_GLYPH_FLAG_*
    uint16_t key_color;
    uint16_t bg_color;
    uint32_t data_offset;
    uint32_t data_size;
    uint32_t data_crc;
} etf_glyph_t;

typedef struct {
    etf_source_t src;
    uint16_t canvas_w;
    uint16_t canvas_h;
    uint16_t glyph_count;
    uint8_t version_minor;
    etf_glyph_t *glyphs; // heap, sorted by code
    uint32_t meta_offset;
    uint32_t meta_size;
} etf_face_t;

/** Streaming decoder state for one glyph. Fields are private. */
typedef struct {
    const etf_face_t *face;
    const etf_glyph_t *glyph;
    uint16_t row;
    uint16_t palette_count;
    uint32_t consumed; // bytes of glyph data read from the source
    uint8_t *in_buf;
    uint16_t in_pos, in_len;
    uint8_t *palette; // palette_count * 2 bytes, big-endian RGB565
    void *inflator;   // tinfl_decompressor
    uint8_t *dict;    // ETF_DEFLATE_DICT ring buffer
    uint16_t dict_ofs, out_pos, out_avail;
    int inflate_status;
} etf_dec_t;

// --- sources ---------------------------------------------------------------------------------

/** Source backed by memory (e.g. an embedded face or a memory-mapped partition). */
void etf_source_from_memory(etf_source_t *src, const void *data, uint32_t size);

/** Source backed by an open FILE (VFS / LittleFS). The file must stay open while in use. */
esp_err_t etf_source_from_file(etf_source_t *src, FILE *f);

// --- face ------------------------------------------------------------------------------------

/**
 * Parse and validate header, glyph table and metadata (spec section 7, items 1-4).
 * Returns ESP_ERR_INVALID_VERSION for an unknown major version, ESP_ERR_INVALID_CRC for a header
 * CRC mismatch, ESP_ERR_INVALID_SIZE / ESP_ERR_INVALID_ARG for structural errors,
 * ESP_ERR_NO_MEM if the glyph table cannot be allocated.
 */
esp_err_t etf_open(etf_face_t *face, const etf_source_t *src);

void etf_close(etf_face_t *face);

/** Glyph for a code point, or NULL. */
const etf_glyph_t *etf_find(const etf_face_t *face, uint32_t code);

/** Check the glyph's data CRC (reads the whole glyph data). */
esp_err_t etf_verify_glyph(const etf_face_t *face, const etf_glyph_t *glyph);

/** Copy the value of a metadata key (NUL-terminated). ESP_ERR_NOT_FOUND if absent. */
esp_err_t etf_meta_get(const etf_face_t *face, const char *key, char *out, size_t out_size);

// --- decoding --------------------------------------------------------------------------------

/** Work buffer size etf_dec_begin() needs for this glyph (any alignment, e.g. plain malloc). */
size_t etf_dec_work_size(const etf_glyph_t *glyph);

esp_err_t etf_dec_begin(etf_dec_t *dec, const etf_face_t *face, const etf_glyph_t *glyph,
                        void *work, size_t work_size);

/**
 * Decode the next row into `out` (glyph->w * 2 bytes, RGB565 big-endian).
 * After the last row the decoder checks that the glyph data was consumed exactly.
 * Returns ESP_ERR_INVALID_STATE when all rows were already decoded.
 */
esp_err_t etf_dec_row(etf_dec_t *dec, uint8_t *out);

/** CRC32 (IEEE 802.3, zlib compatible) as used by the format. */
uint32_t etf_crc32(uint32_t crc, const void *data, size_t len);

#ifdef __cplusplus
}
#endif
