// SPDX-License-Identifier: GPL-3.0-or-later
// ETF clock-face parser and streaming decoder (docs/FORMAT_ETF.md v1.0).

#include "etf.h"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "esp_rom_crc.h"
#include "miniz.h"

#define HEADER_SIZE  32
#define ENTRY_SIZE   32
#define IN_BUF_SIZE  256
#define PALETTE_SIZE 512
#define TMP_SIZE     64

// Corrupt or inconsistent pixel data.
#define ERR_DATA ESP_ERR_INVALID_RESPONSE

static const uint8_t ETF_MAGIC[4] = {'E', 'T', 'F', 0x1A};

static inline uint16_t rd16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1] << 8));
}

static inline uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline size_t align8(size_t n)
{
    return (n + 7) & ~(size_t)7;
}

static inline bool is_palette(uint8_t enc)
{
    return enc == ETF_ENC_PAL8_RLE || enc == ETF_ENC_DEFLATE_PAL8;
}

static inline bool is_deflate(uint8_t enc)
{
    return enc == ETF_ENC_DEFLATE565 || enc == ETF_ENC_DEFLATE_PAL8;
}

static inline bool ranges_overlap(uint32_t a, uint32_t a_len, uint32_t b, uint32_t b_len)
{
    return a_len && b_len && (uint64_t)a < (uint64_t)b + b_len && (uint64_t)b < (uint64_t)a + a_len;
}

uint32_t etf_crc32(uint32_t crc, const void *data, size_t len)
{
    return esp_rom_crc32_le(crc, data, (uint32_t)len);
}

/** Bounds-checked read from the source. */
static esp_err_t src_read(const etf_source_t *src, uint32_t offset, void *buf, size_t len)
{
    if (offset > src->size || len > src->size - offset) {
        return ESP_ERR_INVALID_SIZE;
    }
    return len ? src->read(src->ctx, offset, buf, len) : ESP_OK;
}

static esp_err_t crc_range(const etf_source_t *src, uint32_t offset, uint32_t len, uint32_t *crc)
{
    uint8_t buf[IN_BUF_SIZE];
    while (len) {
        uint32_t n = len < sizeof(buf) ? len : sizeof(buf);
        esp_err_t err = src_read(src, offset, buf, n);
        if (err != ESP_OK) {
            return err;
        }
        *crc = etf_crc32(*crc, buf, n);
        offset += n;
        len -= n;
    }
    return ESP_OK;
}

// --- face ------------------------------------------------------------------------------------

static esp_err_t parse_table(etf_face_t *face, uint32_t table_off, uint32_t *crc)
{
    uint8_t e[ENTRY_SIZE];
    for (uint16_t i = 0; i < face->glyph_count; i++) {
        esp_err_t err = src_read(&face->src, table_off + i * ENTRY_SIZE, e, sizeof(e));
        if (err != ESP_OK) {
            return err;
        }
        *crc = etf_crc32(*crc, e, sizeof(e));
        etf_glyph_t *g = &face->glyphs[i];
        g->code = rd32(e + 0);
        g->x = rd16(e + 4);
        g->y = rd16(e + 6);
        g->w = rd16(e + 8);
        g->h = rd16(e + 10);
        g->encoding = e[12];
        g->flags = e[13];
        g->key_color = rd16(e + 14);
        g->bg_color = rd16(e + 16);
        g->data_offset = rd32(e + 20);
        g->data_size = rd32(e + 24);
        g->data_crc = rd32(e + 28);
    }
    return ESP_OK;
}

static esp_err_t check_glyphs(const etf_face_t *face, uint32_t header_size, uint32_t table_off)
{
    uint32_t table_len = (uint32_t)face->glyph_count * ENTRY_SIZE;
    for (uint16_t i = 0; i < face->glyph_count; i++) {
        const etf_glyph_t *g = &face->glyphs[i];
        if (i > 0 && g->code <= face->glyphs[i - 1].code) {
            return ESP_ERR_INVALID_ARG; // not strictly ascending
        }
        if (g->w < 1 || g->h < 1 || (uint32_t)g->x + g->w > face->canvas_w ||
            (uint32_t)g->y + g->h > face->canvas_h) {
            return ESP_ERR_INVALID_SIZE;
        }
        if ((g->data_offset & 3) || g->data_offset < header_size ||
            g->data_offset > face->src.size || g->data_size > face->src.size - g->data_offset) {
            return ESP_ERR_INVALID_SIZE;
        }
        if (ranges_overlap(g->data_offset, g->data_size, table_off, table_len) ||
            ranges_overlap(g->data_offset, g->data_size, face->meta_offset, face->meta_size)) {
            return ESP_ERR_INVALID_SIZE;
        }
    }
    for (uint32_t d = '0'; d <= '9'; d++) {
        if (!etf_find(face, d)) {
            return ESP_ERR_NOT_FOUND;
        }
    }
    return ESP_OK;
}

esp_err_t etf_open(etf_face_t *face, const etf_source_t *src)
{
    if (!face || !src || !src->read) {
        return ESP_ERR_INVALID_ARG;
    }
    memset(face, 0, sizeof(*face));
    face->src = *src;

    uint8_t h[HEADER_SIZE];
    esp_err_t err = src_read(src, 0, h, sizeof(h));
    if (err != ESP_OK) {
        return err;
    }
    if (memcmp(h, ETF_MAGIC, sizeof(ETF_MAGIC)) != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    if (h[4] != ETF_VERSION_MAJOR) {
        return ESP_ERR_INVALID_VERSION;
    }
    uint32_t header_size = rd16(h + 6);
    face->version_minor = h[5];
    face->canvas_w = rd16(h + 8);
    face->canvas_h = rd16(h + 10);
    face->glyph_count = rd16(h + 12);
    uint32_t table_off = rd32(h + 16);
    face->meta_offset = rd32(h + 20);
    face->meta_size = rd32(h + 24);

    if (header_size < HEADER_SIZE || header_size > src->size) {
        return ESP_ERR_INVALID_SIZE;
    }
    if (face->canvas_w < 1 || face->canvas_w > ETF_MAX_CANVAS || face->canvas_h < 1 ||
        face->canvas_h > ETF_MAX_CANVAS || face->glyph_count < 1 ||
        face->glyph_count > ETF_MAX_GLYPHS) {
        return ESP_ERR_INVALID_SIZE;
    }
    uint64_t table_end = (uint64_t)table_off + (uint64_t)face->glyph_count * ENTRY_SIZE;
    if ((table_off & 3) || table_off < header_size || table_end > src->size) {
        return ESP_ERR_INVALID_SIZE;
    }
    if (face->meta_offset) {
        if (face->meta_size > ETF_MAX_META || face->meta_offset < header_size ||
            (uint64_t)face->meta_offset + face->meta_size > src->size) {
            return ESP_ERR_INVALID_SIZE;
        }
    } else if (face->meta_size) {
        return ESP_ERR_INVALID_SIZE;
    }

    face->glyphs = calloc(face->glyph_count, sizeof(etf_glyph_t));
    if (!face->glyphs) {
        return ESP_ERR_NO_MEM;
    }
    uint32_t crc = etf_crc32(0, h, 28);
    err = parse_table(face, table_off, &crc);
    if (err == ESP_OK && face->meta_offset) {
        err = crc_range(src, face->meta_offset, face->meta_size, &crc);
    }
    if (err == ESP_OK && crc != rd32(h + 28)) {
        err = ESP_ERR_INVALID_CRC;
    }
    if (err == ESP_OK) {
        err = check_glyphs(face, header_size, table_off);
    }
    if (err != ESP_OK) {
        etf_close(face);
    }
    return err;
}

void etf_close(etf_face_t *face)
{
    if (face) {
        free(face->glyphs);
        face->glyphs = NULL;
        face->glyph_count = 0;
    }
}

const etf_glyph_t *etf_find(const etf_face_t *face, uint32_t code)
{
    if (!face || !face->glyphs) {
        return NULL;
    }
    int lo = 0, hi = (int)face->glyph_count - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        uint32_t c = face->glyphs[mid].code;
        if (c == code) {
            return &face->glyphs[mid];
        }
        if (c < code) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return NULL;
}

esp_err_t etf_verify_glyph(const etf_face_t *face, const etf_glyph_t *glyph)
{
    if (!face || !glyph) {
        return ESP_ERR_INVALID_ARG;
    }
    uint32_t crc = 0;
    esp_err_t err = crc_range(&face->src, glyph->data_offset, glyph->data_size, &crc);
    if (err != ESP_OK) {
        return err;
    }
    return crc == glyph->data_crc ? ESP_OK : ESP_ERR_INVALID_CRC;
}

esp_err_t etf_meta_get(const etf_face_t *face, const char *key, char *out, size_t out_size)
{
    if (!face || !key || !out || out_size == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!face->meta_offset || !face->meta_size) {
        return ESP_ERR_NOT_FOUND;
    }
    char *meta = malloc(face->meta_size + 1);
    if (!meta) {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t err = src_read(&face->src, face->meta_offset, meta, face->meta_size);
    if (err != ESP_OK) {
        free(meta);
        return err;
    }
    meta[face->meta_size] = '\0';
    size_t key_len = strlen(key);
    err = ESP_ERR_NOT_FOUND;
    for (char *line = meta; line && *line;) {
        char *next = strchr(line, '\n');
        if (next) {
            *next++ = '\0';
        }
        if (strncmp(line, key, key_len) == 0 && line[key_len] == '=') {
            const char *value = line + key_len + 1;
            size_t len = strlen(value);
            if (len >= out_size) {
                err = ESP_ERR_INVALID_SIZE;
            } else {
                memcpy(out, value, len + 1);
                err = ESP_OK;
            }
            break;
        }
        line = next;
    }
    free(meta);
    return err;
}

// --- decoder: input --------------------------------------------------------------------------

static esp_err_t refill(etf_dec_t *dec)
{
    uint32_t remaining = dec->glyph->data_size - dec->consumed;
    if (remaining == 0) {
        return ERR_DATA; // truncated glyph data
    }
    uint32_t n = remaining < IN_BUF_SIZE ? remaining : IN_BUF_SIZE;
    esp_err_t err =
        src_read(&dec->face->src, dec->glyph->data_offset + dec->consumed, dec->in_buf, n);
    if (err != ESP_OK) {
        return err;
    }
    dec->consumed += n;
    dec->in_pos = 0;
    dec->in_len = (uint16_t)n;
    return ESP_OK;
}

static esp_err_t get_bytes(etf_dec_t *dec, uint8_t *dst, size_t n)
{
    while (n) {
        if (dec->in_pos == dec->in_len) {
            esp_err_t err = refill(dec);
            if (err != ESP_OK) {
                return err;
            }
        }
        size_t k = dec->in_len - dec->in_pos;
        if (k > n) {
            k = n;
        }
        memcpy(dst, dec->in_buf + dec->in_pos, k);
        dec->in_pos += k;
        dst += k;
        n -= k;
    }
    return ESP_OK;
}

static bool input_exhausted(const etf_dec_t *dec)
{
    return dec->in_pos == dec->in_len && dec->consumed == dec->glyph->data_size;
}

// --- decoder: inflate ------------------------------------------------------------------------

/** One tinfl call; output lands in dict[out_pos .. out_pos + out_avail). */
static esp_err_t inflate_step(etf_dec_t *dec)
{
    if (dec->in_pos == dec->in_len && dec->consumed < dec->glyph->data_size) {
        esp_err_t err = refill(dec);
        if (err != ESP_OK) {
            return err;
        }
    }
    size_t in_bytes = dec->in_len - dec->in_pos;
    size_t out_bytes = ETF_DEFLATE_DICT - dec->dict_ofs;
    mz_uint32 flags = dec->consumed < dec->glyph->data_size ? TINFL_FLAG_HAS_MORE_INPUT : 0;
    tinfl_status st = tinfl_decompress(dec->inflator, dec->in_buf + dec->in_pos, &in_bytes,
                                       dec->dict, dec->dict + dec->dict_ofs, &out_bytes, flags);
    dec->in_pos += in_bytes;
    dec->out_pos = dec->dict_ofs;
    dec->out_avail = (uint16_t)out_bytes;
    dec->dict_ofs = (uint16_t)((dec->dict_ofs + out_bytes) & (ETF_DEFLATE_DICT - 1));
    dec->inflate_status = st;
    if (st < 0) {
        return ERR_DATA;
    }
    if (st == TINFL_STATUS_NEEDS_MORE_INPUT && in_bytes == 0 && out_bytes == 0 &&
        input_exhausted(dec)) {
        return ERR_DATA; // stream ends before the expected size
    }
    return ESP_OK;
}

static esp_err_t inflate_bytes(etf_dec_t *dec, uint8_t *dst, size_t n)
{
    while (n) {
        if (dec->out_avail) {
            size_t k = dec->out_avail < n ? dec->out_avail : n;
            memcpy(dst, dec->dict + dec->out_pos, k);
            dec->out_pos += k;
            dec->out_avail -= k;
            dst += k;
            n -= k;
            continue;
        }
        if (dec->inflate_status == TINFL_STATUS_DONE) {
            return ERR_DATA; // decompressed size too small
        }
        esp_err_t err = inflate_step(dec);
        if (err != ESP_OK) {
            return err;
        }
    }
    return ESP_OK;
}

/** After the last row: stream must end here, without extra output or trailing input. */
static esp_err_t inflate_finish(etf_dec_t *dec)
{
    while (dec->inflate_status != TINFL_STATUS_DONE) {
        if (dec->out_avail) {
            return ERR_DATA;
        }
        esp_err_t err = inflate_step(dec);
        if (err != ESP_OK) {
            return err;
        }
    }
    return dec->out_avail == 0 && input_exhausted(dec) ? ESP_OK : ERR_DATA;
}

// --- decoder: rows ---------------------------------------------------------------------------

size_t etf_dec_work_size(const etf_glyph_t *glyph)
{
    if (!glyph) {
        return 0;
    }
    size_t size = align8(IN_BUF_SIZE);
    if (is_palette(glyph->encoding)) {
        size += align8(PALETTE_SIZE);
    }
    if (is_deflate(glyph->encoding)) {
        size += align8(sizeof(tinfl_decompressor)) + ETF_DEFLATE_DICT;
    }
    return size;
}

esp_err_t etf_dec_begin(etf_dec_t *dec, const etf_face_t *face, const etf_glyph_t *glyph,
                        void *work, size_t work_size)
{
    if (!dec || !face || !glyph || !work || ((uintptr_t)work & 7)) {
        return ESP_ERR_INVALID_ARG;
    }
    if (glyph->encoding > ETF_ENC_DEFLATE_PAL8) {
        return ESP_ERR_NOT_SUPPORTED;
    }
    if (work_size < etf_dec_work_size(glyph)) {
        return ESP_ERR_INVALID_SIZE;
    }
    memset(dec, 0, sizeof(*dec));
    dec->face = face;
    dec->glyph = glyph;
    uint8_t *p = work;
    dec->in_buf = p;
    p += align8(IN_BUF_SIZE);
    if (is_palette(glyph->encoding)) {
        dec->palette = p;
        p += align8(PALETTE_SIZE);
        uint8_t cnt[2];
        esp_err_t err = get_bytes(dec, cnt, sizeof(cnt));
        if (err != ESP_OK) {
            return err;
        }
        dec->palette_count = rd16(cnt);
        if (dec->palette_count < 1 || dec->palette_count > 256) {
            return ERR_DATA;
        }
        err = get_bytes(dec, dec->palette, (size_t)dec->palette_count * 2);
        if (err != ESP_OK) {
            return err;
        }
    }
    if (is_deflate(glyph->encoding)) {
        dec->inflator = p;
        p += align8(sizeof(tinfl_decompressor));
        dec->dict = p;
        tinfl_init((tinfl_decompressor *)dec->inflator);
        dec->inflate_status = TINFL_STATUS_NEEDS_MORE_INPUT;
    }
    return ESP_OK;
}

static esp_err_t put_indices(etf_dec_t *dec, const uint8_t *idx, size_t n, uint8_t *out)
{
    for (size_t i = 0; i < n; i++) {
        if (idx[i] >= dec->palette_count) {
            return ERR_DATA;
        }
        out[2 * i] = dec->palette[2 * idx[i]];
        out[2 * i + 1] = dec->palette[2 * idx[i] + 1];
    }
    return ESP_OK;
}

static esp_err_t row_rle(etf_dec_t *dec, uint8_t *out, bool pal)
{
    uint16_t w = dec->glyph->w;
    uint8_t tmp[TMP_SIZE];
    for (uint32_t x = 0; x < w;) {
        uint8_t c;
        esp_err_t err = get_bytes(dec, &c, 1);
        if (err != ESP_OK) {
            return err;
        }
        uint32_t n = (c & 0x7Fu) + 1;
        if (x + n > w) {
            return ERR_DATA; // packet crosses the row end
        }
        uint8_t *dst = out + 2 * x;
        if (c & 0x80u) {
            uint8_t px[2];
            err = pal ? get_bytes(dec, tmp, 1) : get_bytes(dec, px, 2);
            if (err == ESP_OK && pal) {
                err = put_indices(dec, tmp, 1, px);
            }
            if (err != ESP_OK) {
                return err;
            }
            for (uint32_t i = 0; i < n; i++) {
                dst[2 * i] = px[0];
                dst[2 * i + 1] = px[1];
            }
        } else if (!pal) {
            err = get_bytes(dec, dst, 2 * n);
        } else {
            for (uint32_t i = 0; i < n && err == ESP_OK; i += TMP_SIZE) {
                size_t k = n - i < TMP_SIZE ? n - i : TMP_SIZE;
                err = get_bytes(dec, tmp, k);
                if (err == ESP_OK) {
                    err = put_indices(dec, tmp, k, dst + 2 * i);
                }
            }
        }
        if (err != ESP_OK) {
            return err;
        }
        x += n;
    }
    return ESP_OK;
}

static esp_err_t row_deflate_pal8(etf_dec_t *dec, uint8_t *out)
{
    uint8_t tmp[TMP_SIZE];
    uint16_t w = dec->glyph->w;
    for (uint32_t i = 0; i < w; i += TMP_SIZE) {
        size_t k = w - i < TMP_SIZE ? w - i : TMP_SIZE;
        esp_err_t err = inflate_bytes(dec, tmp, k);
        if (err == ESP_OK) {
            err = put_indices(dec, tmp, k, out + 2 * i);
        }
        if (err != ESP_OK) {
            return err;
        }
    }
    return ESP_OK;
}

esp_err_t etf_dec_row(etf_dec_t *dec, uint8_t *out)
{
    if (!dec || !dec->glyph || !out) {
        return ESP_ERR_INVALID_ARG;
    }
    const etf_glyph_t *g = dec->glyph;
    if (dec->row >= g->h) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t err;
    switch (g->encoding) {
        case ETF_ENC_RAW565:
            err = get_bytes(dec, out, (size_t)g->w * 2);
            break;
        case ETF_ENC_RLE565:
            err = row_rle(dec, out, false);
            break;
        case ETF_ENC_PAL8_RLE:
            err = row_rle(dec, out, true);
            break;
        case ETF_ENC_DEFLATE565:
            err = inflate_bytes(dec, out, (size_t)g->w * 2);
            break;
        case ETF_ENC_DEFLATE_PAL8:
            err = row_deflate_pal8(dec, out);
            break;
        default:
            err = ESP_ERR_NOT_SUPPORTED;
            break;
    }
    if (err == ESP_OK && ++dec->row == g->h) {
        if (is_deflate(g->encoding)) {
            err = inflate_finish(dec);
        } else if (!input_exhausted(dec)) {
            err = ERR_DATA; // trailing data after the last row
        }
    }
    if (err != ESP_OK) {
        dec->row = g->h; // further calls fail with ESP_ERR_INVALID_STATE
    }
    return err;
}
