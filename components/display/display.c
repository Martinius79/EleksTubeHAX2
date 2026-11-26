// SPDX-License-Identifier: GPL-3.0-or-later
// Display transport for the chips: SPI via esp_lcd panel IO (no hardware CS), chip select via
// the board's CS backend, panel reset and power.

#include "display.h"

#include <string.h>

#include "cs.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_lcd_panel_io.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "panel.h"

static const char *TAG = "display";

#define SPI_HOST_ID SPI2_HOST
#define FILL_ROWS   16 // rows per fill transfer
#define NO_DIGITS   0

static struct {
    const board_profile_t *board;
    esp_lcd_panel_io_handle_t io;
    SemaphoreHandle_t done; // given when a pixel transfer has finished
    panel_io_t pio;
    bool area_open;
    bool first_write; // next area write carries RAMWR
} s;

static bool on_color_done(esp_lcd_panel_io_handle_t io, esp_lcd_panel_io_event_data_t *edata,
                          void *ctx)
{
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(s.done, &woken);
    return woken == pdTRUE;
}

static esp_err_t io_tx_cmd(void *ctx, uint8_t cmd, const uint8_t *data, size_t len)
{
    return esp_lcd_panel_io_tx_param(s.io, cmd, data, len);
}

static void io_delay(void *ctx, uint32_t ms)
{
    vTaskDelay(pdMS_TO_TICKS(ms ? ms : 1));
}

/** Send pixel bytes and wait until the transfer is complete (CS must stay until then). */
static esp_err_t tx_pixels(int cmd, const uint8_t *data, size_t len)
{
    ESP_RETURN_ON_ERROR(esp_lcd_panel_io_tx_color(s.io, cmd, data, len), TAG, "tx_color");
    return xSemaphoreTake(s.done, pdMS_TO_TICKS(1000)) == pdTRUE ? ESP_OK : ESP_ERR_TIMEOUT;
}

static void panel_reset(int8_t rst)
{
    if (rst == BOARD_PIN_NONE) {
        return;
    }
    gpio_set_level(rst, 1);
    vTaskDelay(pdMS_TO_TICKS(5));
    gpio_set_level(rst, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(rst, 1);
    vTaskDelay(pdMS_TO_TICKS(150));
}

esp_err_t display_power(bool on)
{
    const board_dim_t *dim = s.board ? &s.board->dim : NULL;
    if (!dim || dim->pin == BOARD_PIN_NONE) {
        return s.board ? ESP_OK : ESP_ERR_INVALID_STATE;
    }
    // Full on / off for now; PWM dimming follows in P2.8.
    return gpio_set_level(dim->pin, on != dim->active_low);
}

esp_err_t display_init(const board_profile_t *board)
{
    ESP_RETURN_ON_FALSE(board, ESP_ERR_INVALID_ARG, TAG, "no board");
    ESP_RETURN_ON_FALSE(!s.board, ESP_ERR_INVALID_STATE, TAG, "already initialised");
    ESP_RETURN_ON_ERROR(board_validate(board, NULL, 0), TAG, "invalid profile");
    s.board = board;
    s.done = xSemaphoreCreateBinary();
    ESP_RETURN_ON_FALSE(s.done, ESP_ERR_NO_MEM, TAG, "semaphore");

    ESP_RETURN_ON_ERROR(cs_init(board), TAG, "chip select");

    uint64_t out_mask = 0;
    if (board->spi.rst != BOARD_PIN_NONE) {
        out_mask |= 1ULL << board->spi.rst;
    }
    if (board->dim.pin != BOARD_PIN_NONE) {
        out_mask |= 1ULL << board->dim.pin;
    }
    if (out_mask) {
        gpio_config_t io = {.pin_bit_mask = out_mask, .mode = GPIO_MODE_OUTPUT};
        ESP_RETURN_ON_ERROR(gpio_config(&io), TAG, "gpio");
    }
    ESP_RETURN_ON_ERROR(display_power(true), TAG, "power");

    const size_t frame_bytes = (size_t)board->panel.width * board->panel.height * 2;
    spi_bus_config_t bus = {
        .mosi_io_num = board->spi.mosi,
        .miso_io_num = -1,
        .sclk_io_num = board->spi.sclk,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = (int)frame_bytes,
    };
    ESP_RETURN_ON_ERROR(spi_bus_initialize(SPI_HOST_ID, &bus, SPI_DMA_CH_AUTO), TAG, "spi bus");

    esp_lcd_panel_io_spi_config_t io_cfg = {
        .cs_gpio_num = -1, // chip select is handled by the CS backend
        .dc_gpio_num = board->spi.dc,
        .spi_mode = board->panel.spi_mode,
        .pclk_hz = board->spi.freq_hz,
        .trans_queue_depth = 4,
        .on_color_trans_done = on_color_done,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
    };
    ESP_RETURN_ON_ERROR(
        esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)SPI_HOST_ID, &io_cfg, &s.io), TAG,
        "panel io");
    s.pio = (panel_io_t){.tx_cmd = io_tx_cmd, .delay_ms = io_delay, .ctx = NULL};

    // All panels share reset and receive the init sequence at the same time.
    panel_reset(board->spi.rst);
    ESP_RETURN_ON_ERROR(cs_select(DISPLAY_ALL_DIGITS), TAG, "select");
    esp_err_t err = panel_init_sequence(&s.pio, &board->panel);
    cs_select(NO_DIGITS);
    ESP_RETURN_ON_ERROR(err, TAG, "panel init");

    ESP_LOGI(TAG, "%u panels %ux%u ready (SPI %lu MHz, mode %u)", BOARD_NUM_DIGITS,
             board->panel.width, board->panel.height, (unsigned long)(board->spi.freq_hz / 1000000),
             board->panel.spi_mode);
    return display_fill(DISPLAY_ALL_DIGITS, 0, 0, board->panel.width, board->panel.height, 0x0000);
}

uint16_t display_width(void)
{
    return s.board ? s.board->panel.width : 0;
}

uint16_t display_height(void)
{
    return s.board ? s.board->panel.height : 0;
}

esp_err_t display_area_begin(uint8_t digits, uint16_t x, uint16_t y, uint16_t w, uint16_t h)
{
    ESP_RETURN_ON_FALSE(s.board && !s.area_open, ESP_ERR_INVALID_STATE, TAG, "state");
    ESP_RETURN_ON_FALSE(digits && !(digits & ~DISPLAY_ALL_DIGITS), ESP_ERR_INVALID_ARG, TAG,
                        "digits");
    ESP_RETURN_ON_ERROR(cs_select(digits), TAG, "select");
    esp_err_t err = panel_set_window(&s.pio, &s.board->panel, x, y, w, h);
    if (err != ESP_OK) {
        cs_select(NO_DIGITS);
        return err;
    }
    s.area_open = true;
    s.first_write = true;
    return ESP_OK;
}

esp_err_t display_area_write(const uint8_t *data, size_t len)
{
    ESP_RETURN_ON_FALSE(s.area_open, ESP_ERR_INVALID_STATE, TAG, "no area");
    ESP_RETURN_ON_FALSE(data && len && !(len & 1), ESP_ERR_INVALID_ARG, TAG, "data");
    int cmd = s.first_write ? PANEL_CMD_RAMWR : -1; // later chunks continue the RAM write
    s.first_write = false;
    return tx_pixels(cmd, data, len);
}

esp_err_t display_area_end(void)
{
    ESP_RETURN_ON_FALSE(s.area_open, ESP_ERR_INVALID_STATE, TAG, "no area");
    s.area_open = false;
    return cs_select(NO_DIGITS);
}

esp_err_t display_fill(uint8_t digits, uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                       uint16_t color)
{
    ESP_RETURN_ON_FALSE(s.board, ESP_ERR_INVALID_STATE, TAG, "not initialised");
    size_t rows = h < FILL_ROWS ? h : FILL_ROWS;
    size_t chunk = (size_t)w * rows * 2;
    uint8_t *buf = heap_caps_malloc(chunk, MALLOC_CAP_DMA);
    ESP_RETURN_ON_FALSE(buf, ESP_ERR_NO_MEM, TAG, "fill buffer");
    for (size_t i = 0; i < chunk; i += 2) {
        buf[i] = color >> 8;
        buf[i + 1] = color & 0xFF;
    }
    esp_err_t err = display_area_begin(digits, x, y, w, h);
    for (uint16_t done = 0; err == ESP_OK && done < h; done += rows) {
        size_t n = (h - done < rows ? h - done : rows) * (size_t)w * 2;
        err = display_area_write(buf, n);
    }
    if (s.area_open) {
        esp_err_t end = display_area_end();
        err = err == ESP_OK ? end : err;
    }
    heap_caps_free(buf);
    return err;
}
