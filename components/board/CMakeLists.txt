# SPDX-License-Identifier: GPL-3.0-or-later
# NVS persistence only on the chips; the linux host tests cover the pure selection logic.
if(IDF_TARGET STREQUAL "linux")
    idf_component_register(SRCS "board.c" INCLUDE_DIRS "include")
else()
    idf_component_register(SRCS "board.c" "board_nvs.c"
                           INCLUDE_DIRS "include"
                           PRIV_REQUIRES nvs_flash log)
endif()
