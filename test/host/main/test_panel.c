// SPDX-License-Identifier: GPL-3.0-or-later
// Host tests for the display panel command layer (components/display/panel.c).

#include <string.h>

#include "board.h"
#include "panel.h"
#include "test_groups.h"
#include "unity.h"

#define MAX_LOG 64

typedef struct {
    uint8_t cmd;
    uint8_t len;
    uint8_t data[16];
} logged_t;

typedef struct {
    logged_t log[MAX_LOG];
    int count;
    uint32_t delay_total;
    int fail_at; // command index that returns an error, -1 = never
} mock_t;

static esp_err_t mock_tx(void *ctx, uint8_t cmd, const uint8_t *data, size_t len)
{
    mock_t *m = ctx;
    if (m->count == m->fail_at) {
        return ESP_FAIL;
    }
    TEST_ASSERT_LESS_THAN(MAX_LOG, m->count);
    TEST_ASSERT_LESS_OR_EQUAL(16, len);
    logged_t *l = &m->log[m->count++];
    l->cmd = cmd;
    l->len = (uint8_t)len;
    if (len) {
        memcpy(l->data, data, len);
    }
    return ESP_OK;
}

static void mock_delay(void *ctx, uint32_t ms)
{
    ((mock_t *)ctx)->delay_total += ms;
}

static panel_io_t mock_io(mock_t *m)
{
    memset(m, 0, sizeof(*m));
    m->fail_at = -1;
    return (panel_io_t){.tx_cmd = mock_tx, .delay_ms = mock_delay, .ctx = m};
}

static const logged_t *find_cmd(const mock_t *m, uint8_t cmd)
{
    for (int i = 0; i < m->count; i++) {
        if (m->log[i].cmd == cmd) {
            return &m->log[i];
        }
    }
    return NULL;
}

static board_panel_t gen1_panel(void)
{
    return board_find("ipstube_gen1")->panel;
}

static void test_st7789_init_sequence_gen1(void)
{
    mock_t m;
    panel_io_t io = mock_io(&m);
    board_panel_t p = gen1_panel();
    TEST_ASSERT_EQUAL(ESP_OK, panel_init_sequence(&io, &p));

    TEST_ASSERT_EQUAL_HEX8(PANEL_CMD_SWRESET, m.log[0].cmd);
    TEST_ASSERT_EQUAL_HEX8(PANEL_CMD_SLPOUT, m.log[1].cmd);
    TEST_ASSERT_EQUAL_HEX8(PANEL_CMD_DISPON, m.log[m.count - 1].cmd);
    const logged_t *madctl = find_cmd(&m, PANEL_CMD_MADCTL);
    TEST_ASSERT_NOT_NULL(madctl);
    TEST_ASSERT_EQUAL(1, madctl->len);
    TEST_ASSERT_EQUAL_HEX8(0x00, madctl->data[0]); // Gen1: RGB order
    const logged_t *colmod = find_cmd(&m, PANEL_CMD_COLMOD);
    TEST_ASSERT_EQUAL_HEX8(0x55, colmod->data[0]); // 16 bit/pixel
    const logged_t *ramctrl = find_cmd(&m, 0xB0);
    TEST_ASSERT_EQUAL_HEX8(0x00, ramctrl->data[0]); // big-endian pixel data (ETF order)
    TEST_ASSERT_NOT_NULL(find_cmd(&m, PANEL_CMD_INVON));
    TEST_ASSERT_NULL(find_cmd(&m, PANEL_CMD_INVOFF));
    TEST_ASSERT_EQUAL(14, find_cmd(&m, 0xE0)->len);
    TEST_ASSERT_EQUAL(14, find_cmd(&m, 0xE1)->len);
    // reset 150 + sleep out 120 + colmod 10 + inversion 120 + display on 120
    TEST_ASSERT_EQUAL_UINT32(520, m.delay_total);
}

static void test_st7789_bgr_no_inversion(void)
{
    mock_t m;
    panel_io_t io = mock_io(&m);
    board_panel_t p = gen1_panel();
    p.bgr = true;
    p.invert = false;
    TEST_ASSERT_EQUAL(ESP_OK, panel_init_sequence(&io, &p));
    TEST_ASSERT_EQUAL_HEX8(PANEL_MADCTL_BGR, find_cmd(&m, PANEL_CMD_MADCTL)->data[0]);
    TEST_ASSERT_NOT_NULL(find_cmd(&m, PANEL_CMD_INVOFF));
    TEST_ASSERT_NULL(find_cmd(&m, PANEL_CMD_INVON));
}

static void test_unsupported_panel_and_io_errors(void)
{
    mock_t m;
    panel_io_t io = mock_io(&m);
    board_panel_t p = gen1_panel();
    p.type = BOARD_PANEL_ST7735;
    TEST_ASSERT_EQUAL(ESP_ERR_NOT_SUPPORTED, panel_init_sequence(&io, &p));
    TEST_ASSERT_EQUAL(0, m.count);

    io = mock_io(&m);
    m.fail_at = 3;
    p = gen1_panel();
    TEST_ASSERT_EQUAL(ESP_FAIL, panel_init_sequence(&io, &p));
    TEST_ASSERT_EQUAL(3, m.count); // stops at the first error
}

static void test_window_full_panel_without_offset(void)
{
    mock_t m;
    panel_io_t io = mock_io(&m);
    board_panel_t p = gen1_panel();
    TEST_ASSERT_EQUAL(ESP_OK, panel_set_window(&io, &p, 0, 0, 135, 240));
    TEST_ASSERT_EQUAL(2, m.count);
    const uint8_t col[4] = {0x00, 0x00, 0x00, 134};
    const uint8_t row[4] = {0x00, 0x00, 0x00, 239};
    TEST_ASSERT_EQUAL_HEX8(PANEL_CMD_CASET, m.log[0].cmd);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(col, m.log[0].data, 4);
    TEST_ASSERT_EQUAL_HEX8(PANEL_CMD_RASET, m.log[1].cmd);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(row, m.log[1].data, 4);
}

static void test_window_with_cgram_offset(void)
{
    mock_t m;
    panel_io_t io = mock_io(&m);
    board_panel_t p = gen1_panel();
    p.x_offset = 52; // EleksTube / IPSTube S3 panels (v1 CGRAM_OFFSET)
    p.y_offset = 40;
    TEST_ASSERT_EQUAL(ESP_OK, panel_set_window(&io, &p, 10, 200, 20, 40));
    const uint8_t col[4] = {0x00, 62, 0x00, 81};    // 52+10 .. 52+10+19
    const uint8_t row[4] = {0x00, 240, 0x01, 0x17}; // 40+200=240 .. 279 = 0x117
    TEST_ASSERT_EQUAL_HEX8_ARRAY(col, m.log[0].data, 4);
    TEST_ASSERT_EQUAL_HEX8_ARRAY(row, m.log[1].data, 4);
}

static void test_window_rejects_out_of_bounds(void)
{
    mock_t m;
    panel_io_t io = mock_io(&m);
    board_panel_t p = gen1_panel();
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, panel_set_window(&io, &p, 0, 0, 136, 240));
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, panel_set_window(&io, &p, 100, 0, 36, 1));
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, panel_set_window(&io, &p, 0, 239, 1, 2));
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, panel_set_window(&io, &p, 0, 0, 0, 10));
    TEST_ASSERT_EQUAL(0, m.count); // nothing sent
}

void run_panel_tests(void)
{
    RUN_TEST(test_st7789_init_sequence_gen1);
    RUN_TEST(test_st7789_bgr_no_inversion);
    RUN_TEST(test_unsupported_panel_and_io_errors);
    RUN_TEST(test_window_full_panel_without_offset);
    RUN_TEST(test_window_with_cgram_offset);
    RUN_TEST(test_window_rejects_out_of_bounds);
}
