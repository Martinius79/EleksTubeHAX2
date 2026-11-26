# SPDX-License-Identifier: GPL-3.0-or-later
idf_component_register(SRCS "main.c" "display_test.c"
                       INCLUDE_DIRS "."
                       REQUIRES board display etf faces esp_timer esp_app_format heap nvs_flash freertos)
