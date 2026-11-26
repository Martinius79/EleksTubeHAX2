// SPDX-License-Identifier: GPL-3.0-or-later
// Panel command layer (see panel.h).

#include "panel.h"

typedef struct {
    uint8_t cmd;
    uint8_t len;
    uint8_t data[14];
    uint8_t delay_ms;
} panel_cmd_t;

// ST7789 init from EleksTubeHAX v1 (modified TFT_eSPI, ST7789_Init.h), preceded by the software
// reset TFT_eSPI sends. MADCTL and INVON/INVOFF are inserted from the board profile.
static const panel_cmd_t ST7789_INIT[] = {
    {PANEL_CMD_SWRESET, 0, {0}, 150},
    {PANEL_CMD_SLPOUT, 0, {0}, 120},
    {PANEL_CMD_NORON, 0, {0}, 0},
    {0xB6, 2, {0x0A, 0x82}, 0},        // display function control
    {0xB0, 2, {0x00, 0xE0}, 0},        // RAMCTRL: big-endian pixels, 5->6 bit: r0 = r5, b0 = b5
    {PANEL_CMD_COLMOD, 1, {0x55}, 10}, // 16 bit/pixel
    {0xB2, 5, {0x0C, 0x0C, 0x00, 0x33, 0x33}, 0}, // porch control
    {0xB7, 1, {0x35}, 0},                         // gate control VGH/VGL
    {0xBB, 1, {0x28}, 0},                         // VCOM
    {0xC0, 1, {0x0C}, 0},                         // LCM control
    {0xC2, 2, {0x01, 0xFF}, 0},                   // VDV/VRH enable
    {0xC3, 1, {0x10}, 0},                         // VRH
    {0xC4, 1, {0x20}, 0},                         // VDV
    {0xC6, 1, {0x0F}, 0},                         // frame rate 60 Hz
    {0xD0, 2, {0xA4, 0xA1}, 0},                   // power control 1
    {0xE0,
     14,
     {0xD0, 0x00, 0x02, 0x07, 0x0A, 0x28, 0x32, 0x44, 0x42, 0x06, 0x0E, 0x12, 0x14, 0x17},
     0}, // positive gamma
    {0xE1,
     14,
     {0xD0, 0x00, 0x02, 0x07, 0x0A, 0x28, 0x31, 0x54, 0x47, 0x0E, 0x1C, 0x17, 0x1B, 0x1E},
     0}, // negative gamma
};

static esp_err_t send(const panel_io_t *io, uint8_t cmd, const uint8_t *data, size_t len,
                      uint32_t delay)
{
    esp_err_t err = io->tx_cmd(io->ctx, cmd, data, len);
    if (err == ESP_OK && delay) {
        io->delay_ms(io->ctx, delay);
    }
    return err;
}

esp_err_t panel_init_sequence(const panel_io_t *io, const board_panel_t *panel)
{
    if (!io || !panel) {
        return ESP_ERR_INVALID_ARG;
    }
    if (panel->type != BOARD_PANEL_ST7789) {
        return ESP_ERR_NOT_SUPPORTED; // ST7735 follows with P7.5 / P7.9
    }
    esp_err_t err = ESP_OK;
    for (size_t i = 0; err == ESP_OK && i < sizeof(ST7789_INIT) / sizeof(ST7789_INIT[0]); i++) {
        const panel_cmd_t *c = &ST7789_INIT[i];
        err = send(io, c->cmd, c->data, c->len, c->delay_ms);
        if (err == ESP_OK && c->cmd == PANEL_CMD_NORON) {
            uint8_t madctl = panel->bgr ? PANEL_MADCTL_BGR : 0x00; // portrait, no mirroring
            err = send(io, PANEL_CMD_MADCTL, &madctl, 1, 0);
        }
    }
    if (err == ESP_OK) {
        err = send(io, panel->invert ? PANEL_CMD_INVON : PANEL_CMD_INVOFF, NULL, 0, 120);
    }
    if (err == ESP_OK) {
        err = send(io, PANEL_CMD_DISPON, NULL, 0, 120);
    }
    return err;
}

esp_err_t panel_set_window(const panel_io_t *io, const board_panel_t *panel, uint16_t x, uint16_t y,
                           uint16_t w, uint16_t h)
{
    if (!io || !panel || w == 0 || h == 0 || (uint32_t)x + w > panel->width ||
        (uint32_t)y + h > panel->height) {
        return ESP_ERR_INVALID_ARG;
    }
    uint16_t x0 = x + panel->x_offset, x1 = x0 + w - 1;
    uint16_t y0 = y + panel->y_offset, y1 = y0 + h - 1;
    uint8_t col[4] = {x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF};
    uint8_t row[4] = {y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF};
    esp_err_t err = send(io, PANEL_CMD_CASET, col, sizeof(col), 0);
    return err == ESP_OK ? send(io, PANEL_CMD_RASET, row, sizeof(row), 0) : err;
}
