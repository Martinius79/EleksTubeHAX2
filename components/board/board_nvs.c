// SPDX-License-Identifier: GPL-3.0-or-later
// Persistent board selection in NVS (namespace "board", key "profile").

#include <string.h>

#include "board.h"
#include "esp_log.h"
#include "nvs.h"
#include "sdkconfig.h"

static const char *TAG = "board";

#define NVS_NAMESPACE "board"
#define NVS_KEY       "profile"

esp_err_t board_load_id(char *id, size_t id_size)
{
    if (!id || id_size == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    nvs_handle_t h;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &h);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return ESP_ERR_NOT_FOUND;
    }
    if (err != ESP_OK) {
        return err;
    }
    size_t len = id_size;
    err = nvs_get_str(h, NVS_KEY, id, &len);
    nvs_close(h);
    return err == ESP_ERR_NVS_NOT_FOUND ? ESP_ERR_NOT_FOUND : err;
}

esp_err_t board_save_id(const char *id)
{
    const board_profile_t *p = board_find(id);
    if (!p) {
        return ESP_ERR_NOT_FOUND;
    }
    if (p->chip != board_current_chip()) {
        return ESP_ERR_NOT_SUPPORTED;
    }
    nvs_handle_t h;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_set_str(h, NVS_KEY, id);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err;
}

const board_profile_t *board_get_active(void)
{
    char stored[BOARD_ID_MAX_LEN] = "";
    esp_err_t err = board_load_id(stored, sizeof(stored));
    if (err != ESP_OK && err != ESP_ERR_NOT_FOUND) {
        ESP_LOGW(TAG, "reading stored profile failed: %s", esp_err_to_name(err));
    }
    const board_profile_t *p = board_resolve(stored, CONFIG_BOARD_DEFAULT_ID, board_current_chip());
    if (p) {
        ESP_LOGI(TAG, "profile '%s' (%s)%s", p->id, p->name,
                 strcmp(stored, p->id) == 0 ? "" : " - build default");
    } else {
        ESP_LOGW(TAG, "no usable board profile (stored '%s', default '%s') - display stays off",
                 stored, CONFIG_BOARD_DEFAULT_ID);
    }
    return p;
}
