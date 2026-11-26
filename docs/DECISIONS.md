# Architecture decisions

Short decision log. Status: **accepted**, **open** (needs a spike or input), **superseded**.
When a decision changes, add a new entry and mark the old one superseded – do not rewrite history.

| ID | Decision | Status |
|----|----------|--------|
| D-001 | Framework: plain ESP-IDF (current stable), `idf.py` + Component Manager. No Arduino, no PlatformIO. | accepted |
| D-002 | Licence: GPL-3.0 (same as v1). Origin projects (SmittyHalibut, aly-fly, EleksTubeHAX contributors) are credited explicitly in README and `NOTICE.md`. | accepted |
| D-003 | Hardware selected at **runtime** via board profiles stored in NVS; no per-clock `#ifdef`s. Safe mode protects against a wrong profile. | accepted |
| D-004 | Firmware images per **chip × flash size**: esp32-4MB, esp32-8MB, esp32-16MB, esp32s2-4MB, esp32s2-16MB, esp32s3-8MB, esp32c3-4MB. All ESP32 images use DIO flash mode (IPSTube requirement). | superseded by D-016 |
| D-005 | OTA has priority over built-in clock faces: two app slots on every variant; faces are loaded dynamically, minimum one face + embedded fallback. Draft 4 MB layout below. | accepted |
| D-006 | Own clock-face container `.etf` with pluggable encodings (RAW565, RLE565, PAL8_RLE, optional QOI). CLK format dropped; BMP/PNG/JPG only as import formats (browser / Python tool). | accepted |
| D-007 | No compile-time user config (`_USER_DEFINES.h` gone). All settings at runtime: web UI, REST, console, NVS with schema version. Kconfig only for developer options. | accepted |
| D-008 | Control: REST API is the primary interface; MQTT only for Home Assistant. Dropped: WPS, plain MQTT/Smartnest. | accepted |
| D-009 | Web UI: Preact + Vite + TypeScript, responsive, built in CI, served gzip-compressed from flash. PWA instead of a native mobile app. | accepted |
| D-010 | Rendering: LVGL vs. own lightweight compositor – decided by spike P2.7 (RAM on ESP32 without PSRAM is the hard limit). | open |
| D-011 | Web UI / REST authentication (none, optional password, token). | open |
| D-012 | Weather/info provider for P8.7. | open |
| D-013 | Time zone stored as IANA name, converted to POSIX TZ by an embedded table; DST handled by libc. IP geolocation optional. | accepted |
| D-014 | Testing: host unit tests (ESP-IDF `linux` target + Unity) for format, config, TZ, mode logic; golden-image round-trip tests; JS/Python encoder parity. Hardware verification manual. | accepted |
| D-015 | SI HAI clock not supported in v2. | accepted |
| D-016 | Firmware images per **chip × flash size**, defined in `variants/<variant>.sdkconfig`: esp32-4MB, esp32-8MB-dio, esp32-16MB, esp32s2-4MB, esp32s2-16MB, esp32s3-8MB, esp32c3-4MB. Default flash mode **QIO 80 MHz** (shielded modules). Only IPSTube Gen1 (`esp32-8MB-dio`, weak external flash) uses DIO 40 MHz; whether it can run faster is tested in P5.9. Board quirks never become the global default. | accepted |
| D-017 | Partition table at **0x9000** (bootloader headroom: esp32 bootloader had only 0xAD0 bytes free below 0x8000). Final layouts in `partitions/{4,8,16}MB.csv`; NVS 16 KB. Fixes the D-005 draft, where `otadata` overlapped `ota_0`. Changing the offset later forces a full reflash, so it is fixed now. | accepted |
| D-018 | v1 clock faces are **not** shipped: their origin is undocumented and the nixie set is very likely a stock photo (the same faces appear in all extracted vendor firmwares). Built-in faces are rendered procedurally by `tools/facegen` from geometry only; near-identical re-creations of existing images are not made (they would still be derivative works). | accepted |
| D-019 | Licence for generated clock-face images (proposal: CC0-1.0 so anyone can reuse them; alternative CC-BY-4.0). The generator code itself is GPL-3.0-or-later. | open |

## D-005 – draft partition layouts (to be validated in P0.3)

> Superseded by D-017 and `partitions/*.csv`. Kept for history; the draft has an overlap bug
> (`otadata` 0xF000+0x2000 runs into `ota_0` at 0x10000).

4 MB:

| Name | Type | Offset | Size |
|------|------|--------|------|
| nvs | data/nvs | 0x9000 | 0x6000 (24 K) |
| otadata | data/ota | 0xF000 | 0x2000 |
| ota_0 | app | 0x10000 | 0x180000 (1.5 M) |
| ota_1 | app | 0x190000 | 0x180000 (1.5 M) |
| storage | data/littlefs | 0x310000 | 0xE0000 (896 K) |
| coredump | data/coredump | 0x3F0000 | 0x10000 |

8 MB: 2 × 3 MB app, ~1.9 MB storage. 16 MB: 2 × 4 MB app, ~7.9 MB storage.
Web UI assets go either into the app image (embedded) or a small `www` partition – decide in P4.6.
