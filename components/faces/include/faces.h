// SPDX-License-Identifier: GPL-3.0-or-later
// Built-in clock faces embedded in the firmware image.

#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint16_t width;
    uint16_t height;
    const uint8_t *data; // .etf file
    size_t size;
} faces_builtin_t;

typedef struct {
    uint16_t glyphs;         // glyphs checked
    size_t max_work_size;    // largest decoder work buffer needed
    uint32_t decoded_pixels; // pixels decoded in total
} faces_check_stats_t;

/** Number of embedded fallback faces (one per supported display size). */
size_t faces_fallback_count(void);

/** Fallback face by index, or NULL. */
const faces_builtin_t *faces_fallback_at(size_t index);

/** Fallback face for a display size, or NULL if there is none for that size. */
const faces_builtin_t *faces_fallback(uint16_t width, uint16_t height);

/**
 * Open the face, verify every glyph CRC and decode every glyph completely.
 * `stats` may be NULL. Returns the first error.
 */
esp_err_t faces_check(const faces_builtin_t *face, faces_check_stats_t *stats);

#ifdef __cplusplus
}
#endif
