// SPDX-License-Identifier: GPL-3.0-or-later
// Data sources for the ETF decoder: memory and FILE.

#include <string.h>

#include "etf.h"

static esp_err_t mem_read(void *ctx, uint32_t offset, void *buf, size_t len)
{
    memcpy(buf, (const uint8_t *)ctx + offset, len);
    return ESP_OK;
}

void etf_source_from_memory(etf_source_t *src, const void *data, uint32_t size)
{
    src->read = mem_read;
    src->ctx = (void *)data;
    src->size = size;
}

static esp_err_t file_read(void *ctx, uint32_t offset, void *buf, size_t len)
{
    FILE *f = ctx;
    if (fseek(f, (long)offset, SEEK_SET) != 0) {
        return ESP_FAIL;
    }
    return fread(buf, 1, len, f) == len ? ESP_OK : ESP_FAIL;
}

esp_err_t etf_source_from_file(etf_source_t *src, FILE *f)
{
    if (!src || !f || fseek(f, 0, SEEK_END) != 0) {
        return ESP_ERR_INVALID_ARG;
    }
    long size = ftell(f);
    if (size < 0 || (unsigned long)size > UINT32_MAX) {
        return ESP_ERR_INVALID_SIZE;
    }
    src->read = file_read;
    src->ctx = f;
    src->size = (uint32_t)size;
    return ESP_OK;
}
