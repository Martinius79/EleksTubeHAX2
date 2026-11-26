// SPDX-License-Identifier: GPL-3.0-or-later
// Smoke test: proves the host test harness builds and runs.

#include "test_groups.h"
#include "unity.h"

static void test_harness_runs(void)
{
    TEST_ASSERT_EQUAL_INT(4, 2 + 2);
    TEST_ASSERT_EQUAL_STRING_LEN("etf", "etfx", 3);
}

void run_smoke_tests(void)
{
    RUN_TEST(test_harness_runs);
}
