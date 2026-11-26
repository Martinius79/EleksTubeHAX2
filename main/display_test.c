// SPDX-License-Identifier: GPL-3.0-or-later
// Bring-up test for P2.5/P2.6 (temporary until the clock mode exists, P3.6):
//  1. every digit shows its own solid colour (checks chip-select mapping and colour order),
//  2. every digit shows its digit index from the fallback face (checks decode + transfer)
//     and the draw time per glyph is logged.
//
// Expected on a clock with the usual digit order, left to right:
//   colours: white, yellow, blue, green, red, magenta  -  numbers: 5 4 3 2 1 0

#include "display_test.h"

#include <stdlib.h>

#include "display.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "etf.h"
#include "faces.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "display_test";

#define BATCH_ROWS 16

// RGB565: digit 0 (seconds ones) .. 5 (hours tens)
static const uint16_t COLORS[BOARD_NUM_DIGITS] = {0xF81F, 0xF800, 0x07E0, 0x001F, 0xFFE0, 0xFFFF};
static const char *const COLOR_NAMES[BOARD_NUM_DIGITS] = {"magenta", "red",    "green",
                                                          "blue",    "yellow", "white"};

static esp_err_t draw_glyph(uint8_t digits, const etf_face_t *face, const etf_glyph_t *g)
{
    esp_err_t err = display_fill(digits, 0, 0, face->canvas_w, face->canvas_h, g->bg_color);
    if (err != ESP_OK) {
        return err;
    }
    size_t work_size = etf_dec_work_size(g);
    void *work = malloc(work_size);
    uint8_t *rows = heap_caps_malloc((size_t)g->w * 2 * BATCH_ROWS, MALLOC_CAP_DMA);
    if (!work || !rows) {
        free(work);
        heap_caps_free(rows);
        return ESP_ERR_NO_MEM;
    }
    etf_dec_t dec;
    err = etf_dec_begin(&dec, face, g, work, work_size);
    if (err == ESP_OK) {
        err = display_area_begin(digits, g->x, g->y, g->w, g->h);
    }
    for (uint16_t y = 0; err == ESP_OK && y < g->h;) {
        uint16_t n = 0;
        while (err == ESP_OK && n < BATCH_ROWS && y + n < g->h) {
            err = etf_dec_row(&dec, rows + (size_t)n * g->w * 2);
            n++;
        }
        if (err == ESP_OK) {
            err = display_area_write(rows, (size_t)n * g->w * 2);
        }
        y += n;
    }
    display_area_end();
    heap_caps_free(rows);
    free(work);
    return err;
}

void display_test_run(void)
{
    uint16_t w = display_width(), h = display_height();
    for (int d = 0; d < BOARD_NUM_DIGITS; d++) {
        ESP_LOGI(TAG, "digit %d (%s): %s", d,
                 d == 0   ? "seconds ones"
                 : d == 5 ? "hours tens"
                          : "-",
                 COLOR_NAMES[d]);
        display_fill(DISPLAY_DIGIT(d), 0, 0, w, h, COLORS[d]);
    }
    vTaskDelay(pdMS_TO_TICKS(3000));

    const faces_builtin_t *fb = faces_fallback(w, h);
    if (!fb) {
        ESP_LOGW(TAG, "no fallback face for %ux%u", w, h);
        return;
    }
    etf_source_t src;
    etf_source_from_memory(&src, fb->data, (uint32_t)fb->size);
    etf_face_t face;
    if (etf_open(&face, &src) != ESP_OK) {
        ESP_LOGE(TAG, "fallback face does not open");
        return;
    }
    // the same glyph on all six panels at once (one transfer, all CS lines active)
    int64_t t0 = esp_timer_get_time();
    esp_err_t err = draw_glyph(DISPLAY_ALL_DIGITS, &face, etf_find(&face, '8'));
    ESP_LOGI(TAG, "all digits '8': %s in %lld us", esp_err_to_name(err), esp_timer_get_time() - t0);
    vTaskDelay(pdMS_TO_TICKS(2000));

    for (int d = 0; d < BOARD_NUM_DIGITS; d++) {
        const etf_glyph_t *g = etf_find(&face, '0' + d);
        t0 = esp_timer_get_time();
        err = draw_glyph(DISPLAY_DIGIT(d), &face, g);
        ESP_LOGI(TAG, "digit %d: glyph '%c' %ux%u enc %u, %s in %lld us", d, '0' + d, g->w, g->h,
                 g->encoding, esp_err_to_name(err), esp_timer_get_time() - t0);
    }
    etf_close(&face);
}
