# SPDX-License-Identifier: GPL-3.0-or-later
# Add a test_<component>.c per component under test and list the component in REQUIRES.
idf_component_register(SRCS "test_main.c" "test_smoke.c"
                       INCLUDE_DIRS "."
                       REQUIRES unity)
