# SPDX-License-Identifier: GPL-3.0-or-later
# panel.c is pure logic (host-tested); the transport needs the chip's SPI and GPIO drivers.
if(IDF_TARGET STREQUAL "linux")
    idf_component_register(SRCS "panel.c"
                           INCLUDE_DIRS "include" "."
                           REQUIRES board)
else()
    idf_component_register(SRCS "panel.c" "display.c" "cs.c"
                           INCLUDE_DIRS "include"
                           PRIV_INCLUDE_DIRS "."
                           REQUIRES board
                           PRIV_REQUIRES esp_lcd esp_driver_spi esp_driver_gpio freertos log)
endif()
