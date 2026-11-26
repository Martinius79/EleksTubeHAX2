// SPDX-License-Identifier: GPL-3.0-or-later
// Chip-select backends. GPIO is implemented; 74HC595 and the I2C expander follow with the
// boards that need them (P7.1, P7.9).

#include "cs.h"

#include "driver/gpio.h"
#include "esp_check.h"

static const char *TAG = "cs";

static const board_profile_t *s_board;

static esp_err_t gpio_select(uint8_t mask)
{
    const board_cs_t *cs = &s_board->cs;
    for (int d = 0; d < BOARD_NUM_DIGITS; d++) {
        bool active = mask & (1u << d);
        ESP_RETURN_ON_ERROR(gpio_set_level(cs->pins[d], active != cs->active_low), TAG, "level");
    }
    return ESP_OK;
}

esp_err_t cs_init(const board_profile_t *board)
{
    ESP_RETURN_ON_FALSE(board, ESP_ERR_INVALID_ARG, TAG, "no board");
    if (board->cs.backend != BOARD_CS_GPIO) {
        ESP_LOGE(TAG, "CS backend %d not implemented yet", board->cs.backend);
        return ESP_ERR_NOT_SUPPORTED;
    }
    s_board = board;
    uint64_t mask = 0;
    for (int d = 0; d < BOARD_NUM_DIGITS; d++) {
        mask |= 1ULL << board->cs.pins[d];
        gpio_reset_pin(board->cs.pins[d]); // detach from any previous function
    }
    gpio_config_t io = {.pin_bit_mask = mask, .mode = GPIO_MODE_OUTPUT};
    ESP_RETURN_ON_ERROR(gpio_config(&io), TAG, "gpio");
    return cs_select(0);
}

esp_err_t cs_select(uint8_t mask)
{
    ESP_RETURN_ON_FALSE(s_board, ESP_ERR_INVALID_STATE, TAG, "not initialised");
    return gpio_select(mask);
}
