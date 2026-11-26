// SPDX-License-Identifier: GPL-3.0-or-later
// Host tests for components/board (profile table, validation, selection).

#include <string.h>

#include "board.h"
#include "test_groups.h"
#include "unity.h"

static board_profile_t gen1_copy(void)
{
    const board_profile_t *p = board_find("ipstube_gen1");
    TEST_ASSERT_NOT_NULL(p);
    return *p;
}

static void expect_invalid(const board_profile_t *p, const char *fragment)
{
    char msg[96] = "";
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, board_validate(p, msg, sizeof(msg)));
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(msg, fragment), msg);
}

static void test_all_profiles_valid_and_unique(void)
{
    TEST_ASSERT_GREATER_OR_EQUAL(1, board_profile_count());
    for (size_t i = 0; i < board_profile_count(); i++) {
        const board_profile_t *p = board_profile_at(i);
        char msg[96] = "";
        TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, board_validate(p, msg, sizeof(msg)), msg);
        TEST_ASSERT_EQUAL_PTR(p, board_find(p->id));
        for (size_t j = 0; j < i; j++) {
            TEST_ASSERT_NOT_EQUAL(0, strcmp(p->id, board_profile_at(j)->id));
        }
    }
    TEST_ASSERT_NULL(board_profile_at(board_profile_count()));
    TEST_ASSERT_NULL(board_find(NULL));
    TEST_ASSERT_NULL(board_find(""));
    TEST_ASSERT_NULL(board_find("no_such_board"));
}

static void test_ipstube_gen1_matches_v1(void)
{
    board_profile_t p = gen1_copy();
    TEST_ASSERT_EQUAL(BOARD_CHIP_ESP32, p.chip);
    TEST_ASSERT_EQUAL(135, p.panel.width);
    TEST_ASSERT_EQUAL(240, p.panel.height);
    TEST_ASSERT_EQUAL(3, p.panel.spi_mode);
    TEST_ASSERT_EQUAL(32, p.spi.mosi);
    TEST_ASSERT_EQUAL(33, p.spi.sclk);
    TEST_ASSERT_EQUAL(25, p.spi.dc);
    TEST_ASSERT_EQUAL(26, p.spi.rst);
    const int8_t cs[BOARD_NUM_DIGITS] = {15, 2, 27, 14, 12, 13}; // v1 lcdEnablePins
    TEST_ASSERT_EQUAL_INT8_ARRAY(cs, p.cs.pins, BOARD_NUM_DIGITS);
    TEST_ASSERT_TRUE(p.cs.active_low);
    TEST_ASSERT_EQUAL(BOARD_DIM_PWM, p.dim.mode);
    TEST_ASSERT_EQUAL(4, p.dim.pin);
    TEST_ASSERT_TRUE(p.dim.active_low);
    TEST_ASSERT_EQUAL(BOARD_INPUT_ONE_BUTTON, p.input.type);
    TEST_ASSERT_EQUAL(0, p.input.mode);
    TEST_ASSERT_EQUAL(BOARD_RTC_DS1302, p.rtc.type);
}

static void test_validation_catches_profile_errors(void)
{
    board_profile_t p = gen1_copy();
    p.cs.pins[3] = 15; // same as cs0
    expect_invalid(&p, "used twice");

    p = gen1_copy();
    p.spi.dc = 7; // SPI flash pin on ESP32
    expect_invalid(&p, "not usable");

    p = gen1_copy();
    p.cs.pins[0] = 20; // does not exist on ESP32
    expect_invalid(&p, "GPIO20 not usable");

    p = gen1_copy();
    p.leds.pin = 35; // input-only
    expect_invalid(&p, "input-only");

    p = gen1_copy();
    p.input.mode = 35; // input-only is fine for a button
    TEST_ASSERT_EQUAL(ESP_OK, board_validate(&p, NULL, 0));

    p = gen1_copy();
    p.cs.pins[5] = BOARD_PIN_NONE;
    expect_invalid(&p, "cs5 missing");

    p = gen1_copy();
    p.dim.pwm_freq_hz = 0;
    expect_invalid(&p, "frequency");

    p = gen1_copy();
    p.chip = BOARD_CHIP_ESP32C3; // GPIO32/33 do not exist on the C3
    expect_invalid(&p, "not usable on esp32c3");
}

static void test_i2c_pins_may_be_shared(void)
{
    board_profile_t p = gen1_copy();
    p.cs.backend = BOARD_CS_I2C_EXPANDER;
    p.cs.sda = 21;
    p.cs.scl = 22;
    p.cs.i2c_addr = 0x20;
    p.rtc.type = BOARD_RTC_DS3231;
    p.rtc.pin_a = 22; // scl, shared with the expander
    p.rtc.pin_b = 21; // sda
    TEST_ASSERT_EQUAL(ESP_OK, board_validate(&p, NULL, 0));
    p.rtc.pin_a = 21; // scl on the sda line: not the same bus role
    expect_invalid(&p, "used twice");
}

static void test_resolve_prefers_stored_then_default(void)
{
    const board_profile_t *gen1 = board_find("ipstube_gen1");
    TEST_ASSERT_EQUAL_PTR(gen1, board_resolve("ipstube_gen1", "", BOARD_CHIP_ESP32));
    TEST_ASSERT_EQUAL_PTR(gen1, board_resolve("unknown", "ipstube_gen1", BOARD_CHIP_ESP32));
    TEST_ASSERT_EQUAL_PTR(gen1, board_resolve(NULL, "ipstube_gen1", BOARD_CHIP_ESP32));
    TEST_ASSERT_NULL(board_resolve("unknown", "", BOARD_CHIP_ESP32));
    // a profile for another chip is never selected, not even as default
    TEST_ASSERT_NULL(board_resolve("ipstube_gen1", "ipstube_gen1", BOARD_CHIP_ESP32S3));
}

void run_board_tests(void)
{
    RUN_TEST(test_all_profiles_valid_and_unique);
    RUN_TEST(test_ipstube_gen1_matches_v1);
    RUN_TEST(test_validation_catches_profile_errors);
    RUN_TEST(test_i2c_pins_may_be_shared);
    RUN_TEST(test_resolve_prefers_stored_then_default);
}
