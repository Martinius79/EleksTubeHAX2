// SPDX-License-Identifier: GPL-3.0-or-later
// Built-in clock faces embedded in the firmware image.

#include "faces.h"

#include <stdlib.h>

#include "etf.h"

extern const uint8_t fallback_135x240_start[] asm("_binary_fallback_135x240_etf_start");
extern const uint8_t fallback_135x240_end[] asm("_binary_fallback_135x240_etf_end");
extern const uint8_t fallback_80x160_start[] asm("_binary_fallback_80x160_etf_start");
extern const uint8_t fallback_80x160_end[] asm("_binary_fallback_80x160_etf_end");

static faces_builtin_t s_fallback[2];

static void init_table(void)
{
    if (s_fallback[0].data) {
        return;
    }
    s_fallback[0] = (faces_builtin_t){135, 240, fallback_135x240_start,
                                      (size_t)(fallback_135x240_end - fallback_135x240_start)};
    s_fallback[1] = (faces_builtin_t){80, 160, fallback_80x160_start,
                                      (size_t)(fallback_80x160_end - fallback_80x160_start)};
}

size_t faces_fallback_count(void)
{
    return sizeof(s_fallback) / sizeof(s_fallback[0]);
}

const faces_builtin_t *faces_fallback_at(size_t index)
{
    init_table();
    return index < faces_fallback_count() ? &s_fallback[index] : NULL;
}

const faces_builtin_t *faces_fallback(uint16_t width, uint16_t height)
{
    for (size_t i = 0; i < faces_fallback_count(); i++) {
        const faces_builtin_t *f = faces_fallback_at(i);
        if (f->width == width && f->height == height) {
            return f;
        }
    }
    return NULL;
}

static esp_err_t decode_glyph(const etf_face_t *face, const etf_glyph_t *g, uint8_t *row,
                              faces_check_stats_t *stats)
{
    size_t work_size = etf_dec_work_size(g);
    void *work = malloc(work_size);
    if (!work) {
        return ESP_ERR_NO_MEM;
    }
    etf_dec_t dec;
    esp_err_t err = etf_dec_begin(&dec, face, g, work, work_size);
    for (uint16_t y = 0; err == ESP_OK && y < g->h; y++) {
        err = etf_dec_row(&dec, row);
    }
    free(work);
    if (err == ESP_OK && stats) {
        stats->glyphs++;
        stats->decoded_pixels += (uint32_t)g->w * g->h;
        if (work_size > stats->max_work_size) {
            stats->max_work_size = work_size;
        }
    }
    return err;
}

esp_err_t faces_check(const faces_builtin_t *builtin, faces_check_stats_t *stats)
{
    if (!builtin) {
        return ESP_ERR_INVALID_ARG;
    }
    if (stats) {
        *stats = (faces_check_stats_t){0};
    }
    etf_source_t src;
    etf_source_from_memory(&src, builtin->data, (uint32_t)builtin->size);
    etf_face_t face;
    esp_err_t err = etf_open(&face, &src);
    if (err != ESP_OK) {
        return err;
    }
    if (face.canvas_w != builtin->width || face.canvas_h != builtin->height) {
        etf_close(&face);
        return ESP_ERR_INVALID_SIZE;
    }
    uint8_t *row = malloc((size_t)face.canvas_w * 2);
    if (!row) {
        etf_close(&face);
        return ESP_ERR_NO_MEM;
    }
    for (uint16_t i = 0; err == ESP_OK && i < face.glyph_count; i++) {
        err = etf_verify_glyph(&face, &face.glyphs[i]);
        if (err == ESP_OK) {
            err = decode_glyph(&face, &face.glyphs[i], row, stats);
        }
    }
    free(row);
    etf_close(&face);
    return err;
}
