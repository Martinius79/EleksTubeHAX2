// SPDX-License-Identifier: GPL-3.0-or-later
// The six digit displays: SPI transport, chip select and panel init for the active board.
//
// Drawing targets a set of digits (bit mask, bit n = digit n, see board.h for the index
// convention); all selected panels receive the same pixels. Pixels are RGB565 big-endian,
// exactly what the ETF decoder produces.
//
//   display_area_begin(DISPLAY_DIGIT(3), x, y, w, h);
//   for each row: display_area_write(row, w * 2);
//   display_area_end();

#pragma once

#include <stddef.h>
#include <stdint.h>

#include "board.h"
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define DISPLAY_DIGIT(n)   ((uint8_t)(1u << (n)))
#define DISPLAY_ALL_DIGITS ((uint8_t)((1u << BOARD_NUM_DIGITS) - 1))

/** Bring up SPI, chip select, power and all panels of the board. */
esp_err_t display_init(const board_profile_t *board);

/** Visible size of one panel (portrait). 0 before display_init(). */
uint16_t display_width(void);
uint16_t display_height(void);

/** Fill an area of the selected digits with one colour (RGB565 value). */
esp_err_t display_fill(uint8_t digits, uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                       uint16_t color);

/** Start writing w*h pixels to an area of the selected digits. */
esp_err_t display_area_begin(uint8_t digits, uint16_t x, uint16_t y, uint16_t w, uint16_t h);

/** Append pixel bytes (any multiple of 2, any number of calls). Blocks until sent. */
esp_err_t display_area_write(const uint8_t *data, size_t len);

/** Finish the area and deselect the digits. */
esp_err_t display_area_end(void);

/** Panels on/off (display power via the board's enable pin, if any). */
esp_err_t display_power(bool on);

#ifdef __cplusplus
}
#endif
