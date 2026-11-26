// SPDX-License-Identifier: GPL-3.0-or-later
// Panel command layer: init sequences and address windows, independent of the transport so it
// can be tested on the host with a recording mock.

#pragma once

#include <stddef.h>
#include <stdint.h>

#include "board.h"
#include "esp_err.h"

#define PANEL_CMD_SWRESET 0x01
#define PANEL_CMD_SLPOUT  0x11
#define PANEL_CMD_NORON   0x13
#define PANEL_CMD_INVOFF  0x20
#define PANEL_CMD_INVON   0x21
#define PANEL_CMD_DISPOFF 0x28
#define PANEL_CMD_DISPON  0x29
#define PANEL_CMD_CASET   0x2A
#define PANEL_CMD_RASET   0x2B
#define PANEL_CMD_RAMWR   0x2C
#define PANEL_CMD_MADCTL  0x36
#define PANEL_CMD_COLMOD  0x3A

#define PANEL_MADCTL_BGR 0x08

typedef struct {
    /** Send a command with parameter bytes (blocking). */
    esp_err_t (*tx_cmd)(void *ctx, uint8_t cmd, const uint8_t *data, size_t len);
    void (*delay_ms)(void *ctx, uint32_t ms);
    void *ctx;
} panel_io_t;

/** Full init sequence for the panel type (all currently selected panels receive it). */
esp_err_t panel_init_sequence(const panel_io_t *io, const board_panel_t *panel);

/**
 * Set the address window for (x, y, w, h) in visible coordinates; adds the panel's RAM offset.
 * The caller then sends PANEL_CMD_RAMWR followed by w*h pixels.
 */
esp_err_t panel_set_window(const panel_io_t *io, const board_panel_t *panel, uint16_t x, uint16_t y,
                           uint16_t w, uint16_t h);
