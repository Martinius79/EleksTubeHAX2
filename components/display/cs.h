// SPDX-License-Identifier: GPL-3.0-or-later
// Chip-select backends for the six panels (board_cs_backend_t).

#pragma once

#include <stdint.h>

#include "board.h"
#include "esp_err.h"

/** Configure the backend of the board and deselect all digits. */
esp_err_t cs_init(const board_profile_t *board);

/** Select exactly the digits in `mask` (bit n = digit n), deselect all others. */
esp_err_t cs_select(uint8_t mask);
