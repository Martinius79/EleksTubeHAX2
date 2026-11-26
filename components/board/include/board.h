// SPDX-License-Identifier: GPL-3.0-or-later
// Board profiles: everything that differs between the supported clocks, selected at runtime
// (D-003). Profiles are const data; no per-clock #ifdefs anywhere else in the firmware.
//
// Digit index convention (same as v1): 0 = seconds ones, 1 = seconds tens, 2 = minutes ones,
// 3 = minutes tens, 4 = hours ones, 5 = hours tens. Per-digit hardware data (e.g. cs.pins[])
// is indexed this way; `digits_reversed` marks boards whose hardware order is mirrored.

#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BOARD_NUM_DIGITS 6
#define BOARD_PIN_NONE   (-1)
#define BOARD_ID_MAX_LEN 24

typedef enum {
    BOARD_CHIP_ESP32,
    BOARD_CHIP_ESP32S2,
    BOARD_CHIP_ESP32S3,
    BOARD_CHIP_ESP32C3,
} board_chip_t;

typedef enum {
    BOARD_PANEL_ST7789,
    BOARD_PANEL_ST7735,
} board_panel_type_t;

typedef enum {
    BOARD_CS_GPIO,         // one GPIO per digit
    BOARD_CS_HC595,        // 74HC595 shift register
    BOARD_CS_I2C_EXPANDER, // I2C IO expander (MarvelTubes Mini)
} board_cs_backend_t;

typedef enum {
    BOARD_DIM_NONE,         // no hardware switch: software dimming only
    BOARD_DIM_SWITCH,       // enable pin switches the panels on/off, software dimming
    BOARD_DIM_PWM,          // PWM on the enable pin dims the panels in hardware
    BOARD_DIM_I2C_EXPANDER, // brightness via the IO expander
} board_dim_mode_t;

typedef enum {
    BOARD_INPUT_BUTTONS,    // left / mode / right / power
    BOARD_INPUT_ONE_BUTTON, // single button (IPSTube)
    BOARD_INPUT_GESTURE,    // APDS9960 (NovelLife SE)
    BOARD_INPUT_TOUCH,      // capacitive touch (DEsign)
} board_input_type_t;

typedef enum {
    BOARD_RTC_NONE,
    BOARD_RTC_DS1302,  // 3-wire: pins sclk, io, ce
    BOARD_RTC_DS3231,  // I2C: pins scl, sda
    BOARD_RTC_RX8025T, // I2C: pins scl, sda
} board_rtc_type_t;

typedef struct {
    board_panel_type_t type;
    uint16_t width, height;      // visible area in portrait orientation
    uint16_t x_offset, y_offset; // position of the visible area in controller RAM
    bool bgr;                    // MADCTL colour order BGR instead of RGB
    bool invert;                 // INVON
    uint8_t spi_mode;            // 0..3
} board_panel_t;

typedef struct {
    int8_t mosi, sclk, dc, rst;
    uint32_t freq_hz;
} board_spi_t;

typedef struct {
    board_cs_backend_t backend;
    bool active_low;
    int8_t pins[BOARD_NUM_DIGITS]; // BOARD_CS_GPIO, by digit index
    int8_t data, clock, latch;     // BOARD_CS_HC595
    int8_t sda, scl;               // BOARD_CS_I2C_EXPANDER
    uint8_t i2c_addr;
} board_cs_t;

typedef struct {
    board_dim_mode_t mode;
    int8_t pin;           // display enable / dimming pin
    bool active_low;      // level (or PWM duty) that turns the panels on
    uint32_t pwm_freq_hz; // BOARD_DIM_PWM
} board_dim_t;

typedef struct {
    int8_t pin;
    uint8_t count;
} board_leds_t;

typedef struct {
    board_input_type_t type;
    int8_t left, mode, right, power; // buttons, active low; ONE_BUTTON uses `mode`
} board_input_t;

typedef struct {
    board_rtc_type_t type;
    int8_t pin_a, pin_b, pin_c; // DS1302: sclk, io, ce - I2C: scl, sda, unused
} board_rtc_t;

typedef struct {
    const char *id;   // stable identifier stored in NVS, e.g. "ipstube_gen1"
    const char *name; // human readable
    board_chip_t chip;
    board_panel_t panel;
    board_spi_t spi;
    board_cs_t cs;
    board_dim_t dim;
    board_leds_t leds;
    board_input_t input;
    board_rtc_t rtc;
    int8_t buzzer;
    bool digits_reversed;
} board_profile_t;

/** Number of built-in profiles. */
size_t board_profile_count(void);

/** Profile by table index, or NULL. */
const board_profile_t *board_profile_at(size_t index);

/** Profile by id, or NULL. */
const board_profile_t *board_find(const char *id);

/** The chip this firmware runs on. */
board_chip_t board_current_chip(void);

const char *board_chip_name(board_chip_t chip);

/**
 * Check a profile for consistency: pins exist on the chip, are not reserved for flash, outputs
 * are not on input-only pins, no pin is used twice. On error, `msg` (if not NULL) receives a
 * short description.
 */
esp_err_t board_validate(const board_profile_t *profile, char *msg, size_t msg_size);

/**
 * Choose the active profile: the stored id if it names a valid profile for `chip`, otherwise the
 * build default `default_id` under the same conditions, otherwise NULL (no display hardware is
 * touched - the safe choice for an unknown board).
 */
const board_profile_t *board_resolve(const char *stored_id, const char *default_id,
                                     board_chip_t chip);

// --- persistent selection (NVS namespace "board", key "profile") ---------------------------

/** Load the stored id into `id` (BOARD_ID_MAX_LEN bytes). ESP_ERR_NOT_FOUND if none. */
esp_err_t board_load_id(char *id, size_t id_size);

/** Store a profile id after checking it exists and matches this chip. */
esp_err_t board_save_id(const char *id);

/** Resolve the active profile from NVS and the build default (CONFIG_BOARD_DEFAULT_ID). */
const board_profile_t *board_get_active(void);

#ifdef __cplusplus
}
#endif
