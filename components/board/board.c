// SPDX-License-Identifier: GPL-3.0-or-later
// Board profile table, validation and selection logic (host-testable, no hardware access).

#include "board.h"

#include <stdio.h>
#include <string.h>

#include "sdkconfig.h"

#define NONE BOARD_PIN_NONE

// clang-format off
static const board_profile_t s_profiles[] = {
    {
        // Values from EleksTubeHAX v1 (include/GLOBAL_DEFINES.h, src/ChipSelect.cpp).
        .id = "ipstube_gen1",
        .name = "IPSTube H401/H402 (Gen1, ESP32)",
        .chip = BOARD_CHIP_ESP32,
        // v1 runs these panels without CGRAM offset and with RGB order (TFT_eSPI couples
        // CGRAM_OFFSET to BGR); SPI mode 3 as in TFT_eSPI for ST7789. Verify in P2.5.
        .panel = {.type = BOARD_PANEL_ST7789, .width = 135, .height = 240,
                  .x_offset = 0, .y_offset = 0, .bgr = false, .invert = true, .spi_mode = 3},
        .spi = {.mosi = 32, .sclk = 33, .dc = 25, .rst = 26, .freq_hz = 40000000},
        .cs = {.backend = BOARD_CS_GPIO, .active_low = true,
               .pins = {15, 2, 27, 14, 12, 13},
               .data = NONE, .clock = NONE, .latch = NONE, .sda = NONE, .scl = NONE},
        // Q1 transistor: GPIO4 low = panels on; PWM dims in hardware. Boards without Q1
        // ignore the pin (always on) - handled as a runtime option in P2.8.
        .dim = {.mode = BOARD_DIM_PWM, .pin = 4, .active_low = true, .pwm_freq_hz = 20000},
        .leds = {.pin = 5, .count = 6}, // 34 with the optional LED stripe (runtime option)
        .input = {.type = BOARD_INPUT_ONE_BUTTON, .left = NONE, .mode = 0, .right = NONE,
                  .power = NONE},
        .rtc = {.type = BOARD_RTC_DS1302, .pin_a = 22, .pin_b = 19, .pin_c = 21},
        .buzzer = NONE,
        .digits_reversed = false,
    },
};
// clang-format on

size_t board_profile_count(void)
{
    return sizeof(s_profiles) / sizeof(s_profiles[0]);
}

const board_profile_t *board_profile_at(size_t index)
{
    return index < board_profile_count() ? &s_profiles[index] : NULL;
}

const board_profile_t *board_find(const char *id)
{
    if (!id || !*id) {
        return NULL;
    }
    for (size_t i = 0; i < board_profile_count(); i++) {
        if (strcmp(s_profiles[i].id, id) == 0) {
            return &s_profiles[i];
        }
    }
    return NULL;
}

board_chip_t board_current_chip(void)
{
#if CONFIG_IDF_TARGET_ESP32S2
    return BOARD_CHIP_ESP32S2;
#elif CONFIG_IDF_TARGET_ESP32S3
    return BOARD_CHIP_ESP32S3;
#elif CONFIG_IDF_TARGET_ESP32C3
    return BOARD_CHIP_ESP32C3;
#else
    return BOARD_CHIP_ESP32; // also the linux host build
#endif
}

const char *board_chip_name(board_chip_t chip)
{
    switch (chip) {
        case BOARD_CHIP_ESP32:
            return "esp32";
        case BOARD_CHIP_ESP32S2:
            return "esp32s2";
        case BOARD_CHIP_ESP32S3:
            return "esp32s3";
        case BOARD_CHIP_ESP32C3:
            return "esp32c3";
    }
    return "?";
}

// --- validation ------------------------------------------------------------------------------

typedef struct {
    int8_t pin;
    const char *role;
    bool output;     // must be able to drive the pin
    const char *bus; // pins may be shared only between roles of the same bus (e.g. "i2c_sda")
} pin_use_t;

/** Pin exists on the chip and is not reserved for the SPI flash. */
static bool pin_usable(board_chip_t chip, int pin)
{
    switch (chip) {
        case BOARD_CHIP_ESP32:
            if (pin < 0 || pin > 39 || pin == 20 || pin == 24 || (pin >= 28 && pin <= 31)) {
                return false;
            }
            return !(pin >= 6 && pin <= 11); // flash
        case BOARD_CHIP_ESP32S2:
            return pin >= 0 && pin <= 46 && !(pin >= 22 && pin <= 25) && !(pin >= 26 && pin <= 32);
        case BOARD_CHIP_ESP32S3:
            return pin >= 0 && pin <= 48 && !(pin >= 22 && pin <= 25) && !(pin >= 26 && pin <= 32);
        case BOARD_CHIP_ESP32C3:
            return pin >= 0 && pin <= 21 && !(pin >= 12 && pin <= 17); // flash
    }
    return false;
}

static bool pin_input_only(board_chip_t chip, int pin)
{
    return (chip == BOARD_CHIP_ESP32 && pin >= 34 && pin <= 39) ||
           (chip == BOARD_CHIP_ESP32S2 && pin == 46);
}

static size_t collect_pins(const board_profile_t *p, pin_use_t *u, size_t max)
{
    size_t n = 0;
#define ADD(pin_, role_, out_, bus_)                                                               \
    do {                                                                                           \
        if ((pin_) != NONE && n < max) {                                                           \
            u[n++] = (pin_use_t){(pin_), (role_), (out_), (bus_)};                                 \
        }                                                                                          \
    } while (0)
    static const char *const cs_names[BOARD_NUM_DIGITS] = {"cs0", "cs1", "cs2",
                                                           "cs3", "cs4", "cs5"};
    ADD(p->spi.mosi, "spi.mosi", true, NULL);
    ADD(p->spi.sclk, "spi.sclk", true, NULL);
    ADD(p->spi.dc, "spi.dc", true, NULL);
    ADD(p->spi.rst, "spi.rst", true, NULL);
    switch (p->cs.backend) {
        case BOARD_CS_GPIO:
            for (int i = 0; i < BOARD_NUM_DIGITS; i++) {
                ADD(p->cs.pins[i], cs_names[i], true, NULL);
            }
            break;
        case BOARD_CS_HC595:
            ADD(p->cs.data, "cs.data", true, NULL);
            ADD(p->cs.clock, "cs.clock", true, NULL);
            ADD(p->cs.latch, "cs.latch", true, NULL);
            break;
        case BOARD_CS_I2C_EXPANDER:
            ADD(p->cs.sda, "cs.sda", true, "i2c_sda");
            ADD(p->cs.scl, "cs.scl", true, "i2c_scl");
            break;
    }
    ADD(p->dim.pin, "dim.pin", true, NULL);
    ADD(p->leds.pin, "leds.pin", true, NULL);
    ADD(p->input.left, "input.left", false, NULL);
    ADD(p->input.mode, "input.mode", false, NULL);
    ADD(p->input.right, "input.right", false, NULL);
    ADD(p->input.power, "input.power", false, NULL);
    switch (p->rtc.type) {
        case BOARD_RTC_NONE:
            break;
        case BOARD_RTC_DS1302:
            ADD(p->rtc.pin_a, "rtc.sclk", true, NULL);
            ADD(p->rtc.pin_b, "rtc.io", true, NULL);
            ADD(p->rtc.pin_c, "rtc.ce", true, NULL);
            break;
        case BOARD_RTC_DS3231:
        case BOARD_RTC_RX8025T:
            ADD(p->rtc.pin_a, "rtc.scl", true, "i2c_scl");
            ADD(p->rtc.pin_b, "rtc.sda", true, "i2c_sda");
            break;
    }
    ADD(p->buzzer, "buzzer", true, NULL);
#undef ADD
    return n;
}

#define FAIL(...)                                                                                  \
    do {                                                                                           \
        if (msg && msg_size) {                                                                     \
            snprintf(msg, msg_size, __VA_ARGS__);                                                  \
        }                                                                                          \
        return ESP_ERR_INVALID_ARG;                                                                \
    } while (0)

esp_err_t board_validate(const board_profile_t *p, char *msg, size_t msg_size)
{
    if (!p || !p->id || !*p->id || strlen(p->id) >= BOARD_ID_MAX_LEN || !p->name) {
        FAIL("missing or too long id/name");
    }
    if (p->panel.width == 0 || p->panel.height == 0 || p->panel.spi_mode > 3) {
        FAIL("bad panel geometry or SPI mode");
    }
    if (p->spi.freq_hz == 0 || p->spi.freq_hz > 80000000) {
        FAIL("bad SPI frequency");
    }
    if (p->spi.mosi == NONE || p->spi.sclk == NONE || p->spi.dc == NONE) {
        FAIL("SPI needs mosi, sclk and dc");
    }
    if (p->cs.backend == BOARD_CS_GPIO) {
        for (int i = 0; i < BOARD_NUM_DIGITS; i++) {
            if (p->cs.pins[i] == NONE) {
                FAIL("cs%d missing", i);
            }
        }
    } else if (p->cs.backend == BOARD_CS_HC595 &&
               (p->cs.data == NONE || p->cs.clock == NONE || p->cs.latch == NONE)) {
        FAIL("hc595 needs data, clock and latch");
    } else if (p->cs.backend == BOARD_CS_I2C_EXPANDER &&
               (p->cs.sda == NONE || p->cs.scl == NONE || p->cs.i2c_addr == 0)) {
        FAIL("i2c expander needs sda, scl and address");
    }
    if ((p->dim.mode == BOARD_DIM_SWITCH || p->dim.mode == BOARD_DIM_PWM) && p->dim.pin == NONE) {
        FAIL("dimming mode needs dim.pin");
    }
    if (p->dim.mode == BOARD_DIM_PWM && p->dim.pwm_freq_hz == 0) {
        FAIL("PWM dimming needs a frequency");
    }
    if (p->leds.count > 0 && p->leds.pin == NONE) {
        FAIL("leds need a pin");
    }
    if (p->input.type == BOARD_INPUT_ONE_BUTTON && p->input.mode == NONE) {
        FAIL("one-button input needs input.mode");
    }

    pin_use_t uses[32];
    size_t n = collect_pins(p, uses, sizeof(uses) / sizeof(uses[0]));
    for (size_t i = 0; i < n; i++) {
        if (!pin_usable(p->chip, uses[i].pin)) {
            FAIL("%s: GPIO%d not usable on %s", uses[i].role, uses[i].pin,
                 board_chip_name(p->chip));
        }
        if (uses[i].output && pin_input_only(p->chip, uses[i].pin)) {
            FAIL("%s: GPIO%d is input-only", uses[i].role, uses[i].pin);
        }
        for (size_t j = 0; j < i; j++) {
            bool shared_bus = uses[i].bus && uses[j].bus && strcmp(uses[i].bus, uses[j].bus) == 0;
            if (uses[i].pin == uses[j].pin && !shared_bus) {
                FAIL("GPIO%d used twice (%s, %s)", uses[i].pin, uses[j].role, uses[i].role);
            }
        }
    }
    return ESP_OK;
}

static const board_profile_t *usable(const char *id, board_chip_t chip)
{
    const board_profile_t *p = board_find(id);
    return p && p->chip == chip && board_validate(p, NULL, 0) == ESP_OK ? p : NULL;
}

const board_profile_t *board_resolve(const char *stored_id, const char *default_id,
                                     board_chip_t chip)
{
    const board_profile_t *p = usable(stored_id, chip);
    return p ? p : usable(default_id, chip);
}
