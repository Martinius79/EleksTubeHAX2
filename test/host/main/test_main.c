// SPDX-License-Identifier: GPL-3.0-or-later
// Host test runner: runs all test groups and exits with the number of failures.

#include <stdlib.h>

#include "test_groups.h"
#include "unity.h"

void setUp(void) {}

void tearDown(void) {}

void app_main(void)
{
    UNITY_BEGIN();
    run_smoke_tests();
    run_etf_tests();
    run_faces_tests();
    exit(UNITY_END());
}
