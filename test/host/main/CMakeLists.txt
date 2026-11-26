# SPDX-License-Identifier: GPL-3.0-or-later
# Add a test_<component>.c per component under test and list the component in REQUIRES.
idf_component_register(SRCS "test_main.c" "test_smoke.c" "test_etf.c" "test_faces.c" "test_board.c"
                       INCLUDE_DIRS "."
                       REQUIRES unity etf faces board)
