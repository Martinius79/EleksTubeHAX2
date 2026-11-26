// SPDX-License-Identifier: GPL-3.0-or-later
// Host tests for components/faces (embedded fallback faces).

#include <string.h>

#include "etf.h"
#include "faces.h"
#include "test_groups.h"
#include "unity.h"

static void test_fallback_for_every_display_size(void)
{
    TEST_ASSERT_EQUAL(2, faces_fallback_count());
    TEST_ASSERT_NOT_NULL(faces_fallback(135, 240));
    TEST_ASSERT_NOT_NULL(faces_fallback(80, 160));
    TEST_ASSERT_NULL(faces_fallback(240, 240));
    TEST_ASSERT_NULL(faces_fallback_at(2));
}

static void test_fallback_faces_verify_and_decode(void)
{
    for (size_t i = 0; i < faces_fallback_count(); i++) {
        const faces_builtin_t *f = faces_fallback_at(i);
        faces_check_stats_t st;
        TEST_ASSERT_EQUAL(ESP_OK, faces_check(f, &st));
        TEST_ASSERT_EQUAL(11, st.glyphs); // 0-9 + blank
        TEST_ASSERT_GREATER_THAN(0, st.decoded_pixels);
        TEST_ASSERT_LESS_OR_EQUAL(32 * 1024, f->size); // keep the app image small
    }
}

static void test_fallback_metadata(void)
{
    const faces_builtin_t *f = faces_fallback(135, 240);
    etf_source_t src;
    etf_source_from_memory(&src, f->data, (uint32_t)f->size);
    etf_face_t face;
    TEST_ASSERT_EQUAL(ESP_OK, etf_open(&face, &src));
    TEST_ASSERT_NOT_NULL(etf_find(&face, ETF_CODE_BLANK));
    char buf[32];
    TEST_ASSERT_EQUAL(ESP_OK, etf_meta_get(&face, "license", buf, sizeof(buf)));
    TEST_ASSERT_EQUAL_STRING("CC0-1.0", buf);
    etf_close(&face);
}

static void test_corrupt_builtin_detected(void)
{
    const faces_builtin_t *f = faces_fallback(80, 160);
    static uint8_t copy[32 * 1024];
    TEST_ASSERT_LESS_OR_EQUAL(sizeof(copy), f->size);
    memcpy(copy, f->data, f->size);
    copy[f->size - 1] ^= 0x01; // last byte belongs to the last glyph's data
    faces_builtin_t bad = {f->width, f->height, copy, f->size};
    TEST_ASSERT_EQUAL(ESP_ERR_INVALID_CRC, faces_check(&bad, NULL));
}

void run_faces_tests(void)
{
    RUN_TEST(test_fallback_for_every_display_size);
    RUN_TEST(test_fallback_faces_verify_and_decode);
    RUN_TEST(test_fallback_metadata);
    RUN_TEST(test_corrupt_builtin_detected);
}
