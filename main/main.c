// SPDX-License-Identifier: GPL-3.0-or-later
// EleksTubeHAX2 - firmware entry point.

#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_log.h"

static const char *TAG = "main";

void app_main(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    esp_chip_info_t chip;
    esp_chip_info(&chip);

    ESP_LOGI(TAG, "EleksTubeHAX2 %s (IDF %s), chip model %d rev %d, %d core(s)",
             app->version, app->idf_ver, chip.model, chip.revision, chip.cores);
}
