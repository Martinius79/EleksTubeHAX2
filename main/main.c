// SPDX-License-Identifier: GPL-3.0-or-later
// EleksTubeHAX2 - firmware entry point.

#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "faces.h"

static const char *TAG = "main";

/** Verify and fully decode the embedded fallback faces; logs timing as a first benchmark. */
static void check_builtin_faces(void)
{
    for (size_t i = 0; i < faces_fallback_count(); i++) {
        const faces_builtin_t *f = faces_fallback_at(i);
        faces_check_stats_t st;
        int64_t t0 = esp_timer_get_time();
        esp_err_t err = faces_check(f, &st);
        int64_t us = esp_timer_get_time() - t0;
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "fallback face %ux%u: %s", f->width, f->height, esp_err_to_name(err));
            continue;
        }
        ESP_LOGI(TAG,
                 "fallback face %ux%u: %u bytes, %u glyphs OK, %lld us (%lld us/glyph), "
                 "work buffer %u bytes",
                 f->width, f->height, (unsigned)f->size, st.glyphs, us,
                 us / (st.glyphs ? st.glyphs : 1), (unsigned)st.max_work_size);
    }
}

void app_main(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    esp_chip_info_t chip;
    esp_chip_info(&chip);

    ESP_LOGI(TAG, "EleksTubeHAX2 %s (IDF %s), chip model %d rev %d, %d core(s)", app->version,
             app->idf_ver, chip.model, chip.revision, chip.cores);

    check_builtin_faces();
    ESP_LOGI(TAG, "free heap %u bytes, largest block %u bytes",
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
}
