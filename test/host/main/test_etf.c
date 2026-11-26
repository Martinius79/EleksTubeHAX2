// SPDX-License-Identifier: GPL-3.0-or-later
// Host tests for components/etf against the shared fixtures (test/host/fixtures).

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "etf.h"
#include "test_groups.h"
#include "unity.h"

#define FIXTURES "fixtures/"

static uint8_t *load_file(const char *path, size_t *size)
{
    FILE *f = fopen(path, "rb");
    if (!f) {
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = malloc(n > 0 ? (size_t)n : 1);
    if (buf && fread(buf, 1, (size_t)n, f) != (size_t)n) {
        free(buf);
        buf = NULL;
    }
    fclose(f);
    *size = (size_t)n;
    return buf;
}

/** Decode a glyph onto a full canvas (bg fill + glyph rectangle), big-endian RGB565. */
static esp_err_t render_glyph(const etf_face_t *face, const etf_glyph_t *g, uint8_t *canvas)
{
    for (uint32_t i = 0; i < (uint32_t)face->canvas_w * face->canvas_h; i++) {
        canvas[2 * i] = g->bg_color >> 8;
        canvas[2 * i + 1] = g->bg_color & 0xFF;
    }
    size_t work_size = etf_dec_work_size(g);
    void *work = malloc(work_size);
    uint8_t *row = malloc((size_t)g->w * 2);
    TEST_ASSERT_NOT_NULL(work);
    TEST_ASSERT_NOT_NULL(row);
    etf_dec_t dec;
    esp_err_t err = etf_dec_begin(&dec, face, g, work, work_size);
    for (uint16_t y = 0; err == ESP_OK && y < g->h; y++) {
        err = etf_dec_row(&dec, row);
        if (err == ESP_OK) {
            memcpy(canvas + 2 * ((size_t)(g->y + y) * face->canvas_w + g->x), row,
                   (size_t)g->w * 2);
        }
    }
    free(row);
    free(work);
    return err;
}

typedef enum { OUT_OK, OUT_OPEN_ERROR, OUT_CRC_ERROR, OUT_DECODE_ERROR } outcome_t;

static void check_fixture(const char *name, outcome_t expected, bool use_file_source)
{
    char path[128];
    snprintf(path, sizeof(path), FIXTURES "%s.etf", name);
    size_t size = 0;
    uint8_t *data = load_file(path, &size);
    TEST_ASSERT_NOT_NULL_MESSAGE(data, path);

    etf_source_t src;
    FILE *f = NULL;
    if (use_file_source) {
        f = fopen(path, "rb");
        TEST_ASSERT_EQUAL(ESP_OK, etf_source_from_file(&src, f));
    } else {
        etf_source_from_memory(&src, data, (uint32_t)size);
    }

    etf_face_t face;
    esp_err_t err = etf_open(&face, &src);
    if (expected == OUT_OPEN_ERROR) {
        TEST_ASSERT_NOT_EQUAL_MESSAGE(ESP_OK, err, name);
        TEST_ASSERT_NULL(face.glyphs);
    } else {
        TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, name);
        bool crc_failed = false, decode_failed = false;
        size_t canvas_bytes = (size_t)face.canvas_w * face.canvas_h * 2;
        uint8_t *canvas = malloc(canvas_bytes);
        size_t expect_size = 0;
        uint8_t *expect = NULL;
        if (expected == OUT_OK) {
            snprintf(path, sizeof(path), FIXTURES "%s.expect", name);
            expect = load_file(path, &expect_size);
            TEST_ASSERT_NOT_NULL_MESSAGE(expect, path);
            TEST_ASSERT_EQUAL(canvas_bytes * face.glyph_count, expect_size);
        }
        for (uint16_t i = 0; i < face.glyph_count; i++) {
            const etf_glyph_t *g = &face.glyphs[i];
            if (etf_verify_glyph(&face, g) != ESP_OK) {
                crc_failed = true;
                continue;
            }
            if (render_glyph(&face, g, canvas) != ESP_OK) {
                decode_failed = true;
                continue;
            }
            if (expect) {
                TEST_ASSERT_EQUAL_HEX8_ARRAY_MESSAGE(expect + i * canvas_bytes, canvas,
                                                     canvas_bytes, name);
            }
        }
        TEST_ASSERT_EQUAL_MESSAGE(expected == OUT_CRC_ERROR, crc_failed, name);
        TEST_ASSERT_EQUAL_MESSAGE(expected == OUT_DECODE_ERROR, decode_failed, name);
        free(expect);
        free(canvas);
        etf_close(&face);
    }
    if (f) {
        fclose(f);
    }
    free(data);
}

static void run_manifest(bool use_file_source)
{
    size_t size = 0;
    char *manifest = (char *)load_file(FIXTURES "manifest.txt", &size);
    TEST_ASSERT_NOT_NULL_MESSAGE(manifest, "run from test/host (fixtures/ missing)");
    manifest = realloc(manifest, size + 1);
    manifest[size] = '\0';
    int count = 0;
    char *save = NULL;
    for (char *line = strtok_r(manifest, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char name[64], outcome[32];
        TEST_ASSERT_EQUAL(2, sscanf(line, "%63s %31s", name, outcome));
        outcome_t exp = !strcmp(outcome, "ok")             ? OUT_OK
                        : !strcmp(outcome, "open_error")   ? OUT_OPEN_ERROR
                        : !strcmp(outcome, "crc_error")    ? OUT_CRC_ERROR
                        : !strcmp(outcome, "decode_error") ? OUT_DECODE_ERROR
                                                           : -1;
        TEST_ASSERT_NOT_EQUAL_MESSAGE(-1, (int)exp, line);
        check_fixture(name, exp, use_file_source);
        count++;
    }
    free(manifest);
    TEST_ASSERT_GREATER_OR_EQUAL(20, count);
}

static void test_fixtures_memory_source(void)
{
    run_manifest(false);
}

static void test_fixtures_file_source(void)
{
    run_manifest(true);
}

static void test_crc32_matches_zlib(void)
{
    TEST_ASSERT_EQUAL_HEX32(0xCBF43926, etf_crc32(0, "123456789", 9));
    uint32_t crc = etf_crc32(0, "12345", 5); // running CRC over several buffers
    TEST_ASSERT_EQUAL_HEX32(0xCBF43926, etf_crc32(crc, "6789", 4));
}

static void test_find_meta_and_extra_glyphs(void)
{
    size_t size;
    uint8_t *data = load_file(FIXTURES "auto_cropped.etf", &size);
    TEST_ASSERT_NOT_NULL(data);
    etf_source_t src;
    etf_source_from_memory(&src, data, (uint32_t)size);
    etf_face_t face;
    TEST_ASSERT_EQUAL(ESP_OK, etf_open(&face, &src));
    TEST_ASSERT_EQUAL(11, face.glyph_count);
    for (uint32_t c = '0'; c <= '9'; c++) {
        const etf_glyph_t *g = etf_find(&face, c);
        TEST_ASSERT_NOT_NULL(g);
        TEST_ASSERT_EQUAL_UINT32(c, g->code);
    }
    TEST_ASSERT_NOT_NULL(etf_find(&face, ETF_CODE_COLON));
    TEST_ASSERT_NULL(etf_find(&face, ETF_CODE_AM));
    TEST_ASSERT_NULL(etf_find(&face, 0));
    TEST_ASSERT_NULL(etf_find(&face, 0xFFFFFFFF));
    // cropping: the details pattern has a black border, so glyphs are smaller than the canvas
    const etf_glyph_t *g = etf_find(&face, '0');
    TEST_ASSERT_LESS_THAN(face.canvas_w * face.canvas_h, g->w * g->h);

    char buf[32];
    TEST_ASSERT_EQUAL(ESP_OK, etf_meta_get(&face, "name", buf, sizeof(buf)));
    TEST_ASSERT_EQUAL_STRING("fixture", buf);
    TEST_ASSERT_EQUAL(ESP_OK, etf_meta_get(&face, "license", buf, sizeof(buf)));
    TEST_ASSERT_EQUAL_STRING("CC0-1.0", buf);
    TEST_ASSERT_EQUAL(ESP_ERR_NOT_FOUND, etf_meta_get(&face, "nam", buf, sizeof(buf)));
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_SIZE, etf_meta_get(&face, "name", buf, 4));
    etf_close(&face);
    free(data);
}

static void test_api_misuse(void)
{
    size_t size;
    uint8_t *data = load_file(FIXTURES "deflate565.etf", &size);
    TEST_ASSERT_NOT_NULL(data);
    etf_source_t src;
    etf_source_from_memory(&src, data, (uint32_t)size);
    etf_face_t face;
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, etf_open(NULL, &src));
    TEST_ASSERT_EQUAL(ESP_OK, etf_open(&face, &src));
    const etf_glyph_t *g = etf_find(&face, '1');
    size_t need = etf_dec_work_size(g);
    TEST_ASSERT_GREATER_THAN(ETF_DEFLATE_DICT, need);

    uint64_t *work = calloc(need / 8 + 2, 8);
    etf_dec_t dec;
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_SIZE, etf_dec_begin(&dec, &face, g, work, need - 1));
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_ARG, etf_dec_begin(&dec, &face, g, NULL, need));
    // any alignment works: the decoder aligns the buffer itself
    TEST_ASSERT_EQUAL(ESP_OK, etf_dec_begin(&dec, &face, g, (uint8_t *)work + 1, need));
    uint8_t row[2 * 64];
    for (uint16_t y = 0; y < g->h; y++) {
        TEST_ASSERT_EQUAL(ESP_OK, etf_dec_row(&dec, row));
    }
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_STATE, etf_dec_row(&dec, row));
    free(work);
    etf_close(&face);

    // a source that is shorter than the header claims
    etf_source_from_memory(&src, data, 20);
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_SIZE, etf_open(&face, &src));
    free(data);
}

void run_etf_tests(void)
{
    RUN_TEST(test_crc32_matches_zlib);
    RUN_TEST(test_fixtures_memory_source);
    RUN_TEST(test_fixtures_file_source);
    RUN_TEST(test_find_meta_and_extra_glyphs);
    RUN_TEST(test_api_misuse);
}
