# EleksTubeHAX2 – Roadmap

Living work plan for the ESP-IDF rewrite. Work through it top to bottom; tick boxes as tasks are
finished and note anything surprising under *Progress log*. Architecture decisions live in
[DECISIONS.md](DECISIONS.md) – change a decision there first, then update this plan.

**Current focus:** Phase 0 – project skeleton
**Reference hardware:** IPSTube H401/H402 Gen1 (ESP32, 8 MB, no LED stripe, with Q1 transistor)
**Predecessor:** [EleksTubeHAX v1](https://github.com/aly-fly/EleksTubeHAX) – hardware knowledge
source (`include/GLOBAL_DEFINES.h`, `src/ChipSelect.cpp`, `src/Clock.cpp`, `docs/Hardware *`)

Task format: `- [ ] ID – task` · *Done when* = acceptance criterion · *Needs* = dependency.
Tasks marked 🔌 need physical hardware; everything else can be done without a clock.

---

## Phase 0 – Project skeleton 

- [x] **P0.1** – Toolchain: ESP-IDF (current stable) via EIM, VS Code ESP-IDF extension, `gh` CLI.
  *Done when* `idf.py --version` works in the ESP-IDF PowerShell.
- [x] **P0.2** – Repo layout: `main/`, `components/`, `web/`, `tools/`, `test/host/`, `docs/`,
  `partitions/`, `sdkconfig.defaults` + `sdkconfig.defaults.<target>`.
  *Done when* an empty `app_main` builds for esp32, esp32s2, esp32s3, esp32c3.
- [x] **P0.3** – Image variants (chip × flash) via `variants/<variant>.sdkconfig` and one
  partition table per flash size (see D-016, D-017). Build helper `tools/build.py <variant>`.
- [x] **P0.4** – `.gitattributes` (LF; CRLF for `*.cmd`/`*.bat`), `.gitignore` for `build/`,
  `managed_components/`, `sdkconfig`, `web/node_modules/`, `web/dist/`.
- [ ] **P0.5** – Licence & attribution: GPL-3.0 kept, `NOTICE.md` naming SmittyHalibut,
  aly-fly and all EleksTubeHAX contributors; SPDX headers in source files.
- [ ] **P0.6** – `AGENTS.md` / contributor rules (language, git rules, build vs. flash policy).
- [ ] **P0.7** – CI (GitHub Actions, `espressif/esp-idf-ci-action`): build matrix of all
  variants, host tests (P0.8), web UI build (P4.6). Artifacts per variant.
- [ ] **P0.8** – Host test harness: components built for the `linux` target with Unity,
  run by `idf.py --preview set-target linux` + `ctest`/test runner in CI.
  *Done when* one dummy test runs locally and in CI.
- [ ] **P0.9** – Coding style: `.clang-format`, `.editorconfig`; naming conventions in AGENTS.md.

## Phase 1 – Clock-face image format (`.etf`) 

- [ ] **P1.1** – Write the format spec `docs/FORMAT_ETF.md`: header (magic, version, w/h,
  glyph count, glyph table with offsets), encodings `RAW565`, `RLE565`, `PAL8_RLE`, (`QOI` optional),
  per-glyph encoding allowed. Glyphs 0–9 required; optional `:`, blank, AM/PM, icons.
- [ ] **P1.2** – C decoder component `components/etf`: streaming, line by line into a caller
  buffer (no full frame needed), bounds-checked against corrupt files.
- [ ] **P1.3** – Python encoder `tools/etf/` (Pillow): resize, quantise, choose the smallest
  encoding automatically, CLI `etf encode <dir|images> -o face.etf --size 135x240`.
- [ ] **P1.4** – Test images `test/images/` (solid, gradient, noise, >256 colours, 1px details,
  transparency) + golden outputs.
- [ ] **P1.5** – Host tests: round trip encoder→decoder pixel-exact (lossless modes),
  corrupt/truncated file handling, size budget report per encoding.
- [ ] **P1.6** – Convert the v1 clock faces (`data/*.bmp`) to `.etf` in both sizes; record
  sizes per encoding in the progress log.
  *Done when* all v1 faces fit and the smallest-encoding choice is documented.

## Phase 2 – Board abstraction & display 🔌

- [ ] **P2.1** – `components/board`: profile struct (chip, display type/size/offsets/colour
  order/inversion, SPI pins + freq, CS backend + pins, enable/dimming pin + mode, LED pin/count,
  input type + pins, RTC type + pins, buzzer, digit order). Profiles as const table.
- [ ] **P2.2** – Profile `ipstube_gen1` from v1 data (see *Hardware notes*).
- [ ] **P2.3** – Profile selection: NVS key `board.profile`; compile-time default per variant;
  console command `board set <id>`.
- [ ] **P2.4** – `components/display`: `esp_lcd` SPI panel IO, ST7789 driver, init of all six
  panels, CS backend interface with `gpio` implementation (`hc595`, `i2c_expander` later).
- [ ] **P2.5** 🔌 – Draw a test pattern on each digit, then a decoded `.etf` glyph per digit.
- [ ] **P2.6** 🔌 – Benchmark: decode + transfer time per digit and encoding, free heap,
  largest free block. Record in progress log.
- [ ] **P2.7** 🔌 – Rendering spike: LVGL (6 displays, partial buffers) vs. own compositor.
  Criteria: RAM on ESP32 without PSRAM, flash size, frame time, effort for text/menu.
  Write result as decision D-010.
- [ ] **P2.8** 🔌 – Display brightness: LEDC PWM on the enable pin (Q1 transistor), panel
  on/off. Software alpha dimming as fallback for boards without hardware dimming.

## Phase 3 – Clock core 🔌

- [ ] **P3.1** – `components/config`: typed NVS access, schema version + migration functions,
  defaults, change events via `esp_event`, delayed write (debounce like v1 `markDirty`).
  Host tests for migration.
- [ ] **P3.2** – `components/timekeeping`: SNTP, POSIX TZ via `setenv/tzset`, embedded
  IANA→POSIX table (generated by script from tzdata, host-tested), time source state.
- [ ] **P3.3** – RTC drivers behind one interface: `ds1302` (3-wire), later `ds3231`,
  `rx8025t`, `none`. Read on boot, write after successful SNTP sync.
- [ ] **P3.4** – `components/backlight`: `led_strip` (RMT), effects (off, constant, rainbow,
  pulse, breath), intensity, configurable direction per profile (v1 TODO).
- [ ] **P3.5** – `components/input`: `espressif/button` wrapper → unified events
  (left/right/mode/power, short/long/double). One-button scheme for IPSTube.
- [ ] **P3.6** – `components/modes` + mode manager (state machine) and the **clock mode**
  (12/24 h, blank leading zero, face selection).
- [ ] **P3.7** – Night mode: times and levels (TFT + backlight) in NVS; manual changes during
  the night persist until the next day period (v1 TODOs: no hourly reset, backlight adjustable).
- [ ] **P3.8** – On-device menu (basic, text based) for the settings above.
  *Done when* the IPSTube runs as a standalone clock without WiFi config (RTC time).

## Phase 4 – Network, setup, REST & web UI 🔌

- [ ] **P4.1** – `components/net`: WiFi STA with reconnect/backoff, status events, status icons
  on the display.
- [ ] **P4.2** – Provisioning: SoftAP + captive portal (DNS redirect) when no credentials;
  Improv-WiFi over serial (for ESP Web Tools).
- [ ] **P4.3** – mDNS `elekstube-<mac3>.local`, device ID scheme as in v1
  (`lower(name)-<last3MACbytes>`).
- [ ] **P4.4** – `esp_console` CLI over UART/USB-CDC: `wifi`, `board`, `config get/set`,
  `face`, `reboot`, `bench` (v1 TODO "config via serial terminal").
- [ ] **P4.5** – REST API (`esp_http_server`): `/api/status`, `/api/config` (GET/PATCH),
  `/api/faces` (list/upload/delete/select), `/api/wifi`, `/api/ota`, `/api/system`.
  Spec in `docs/API.md` (OpenAPI optional). Auth: optional password (D-011, open).
- [ ] **P4.6** – Web UI `web/` (Preact + Vite + TypeScript), responsive, gzip, served from a
  dedicated partition or embedded; built in CI.
- [ ] **P4.7** – Face upload in the browser: canvas resize to the device size, JS `.etf`
  encoder (bit-identical to Python, parity test in CI), preview, upload.
- [ ] **P4.8** – Face storage management on LittleFS: quota, delete, at least one face always
  present (built-in fallback face embedded in the app).
- [ ] **P4.9** – Timezone: picker in the web UI + optional one-shot/weekly IP geolocation
  (ip-api.com, returns IANA name).

## Phase 5 – OTA, web flasher, robustness 🔌

- [ ] **P5.1** – OTA via web upload (`esp_ota_ops`) with app rollback (mark valid after
  successful boot + display init).
- [ ] **P5.2** – OTA pull from GitHub Releases (`esp_https_ota`, manifest per variant,
  version check, opt-in auto update).
- [ ] **P5.3** – Safe mode: boot counter in RTC memory/NVS; after 3 failed boots start only
  AP + web UI, peripherals off, offer profile selection.
- [ ] **P5.4** – Web flasher on GitHub Pages (ESP Web Tools): manifest per variant, profile
  choice before flashing, Improv WiFi afterwards (v1 TODO "flash from the browser").
- [ ] **P5.5** – Release workflow: tag → CI builds all variants → GitHub Release + Pages update.
- [ ] **P5.6** – Factory reset (long press at boot + API + console).
- [ ] **P5.7** – Core dump partition + `/api/system/coredump` download.
- [ ] **P5.8** 🔌 – Long-run test setup: serial log capture with timestamps, periodic heap /
  uptime / reset-reason / WiFi stats over console or REST, crash + core dump collection.
  *Done when* a clock can run unattended for days and a report shows resets and heap trend.
- [ ] **P5.9** 🔌 – IPSTube Gen1 flash tuning: with the P5.8 setup try faster SDK settings
  (DIO 80 MHz, QIO/QOUT, flash/SPI timing options) and check for stable operation over days.
  Result updates D-016 and the `esp32-8MB-dio` variant. *Needs* P5.8.

## Phase 6 – Home Assistant 🔌

- [ ] **P6.1** – `components/mqtt_ha` with `esp-mqtt` (TLS optional), broker config via web UI.
- [ ] **P6.2** – HA discovery (light, select, number, switch, sensor) – check v1 entity set
  and keep `unique_id`s compatible where sensible.
- [ ] **P6.3** – One JSON state topic per device, batched updates (v1 TODO).
- [ ] **P6.4** – Commands mapped onto the same internal API as REST (no duplicate logic).

## Phase 7 – Remaining boards (one task = profile + missing drivers + hardware test)

| ID | Clock | Image variant | New parts needed |
|----|-------|---------------|------------------|
| P7.1 | EleksTube (orig.) | esp32-4MB | `hc595` CS backend, `ds3231` |
| P7.2 | EleksTube Gen2 | esp32-4MB | – (different pins) |
| P7.3 | PunkCyber | esp32-4MB | – (= EleksTube, reversed digits) |
| P7.4 | NovelLife SE | esp32-4MB | `rx8025t`, APDS9960 input (gain 1×, fake ID), buzzer |
| P7.5 | DEsign | esp32-4MB | ST7735S 80×160 BGR, touch input, buzzer, `ds3231` |
| P7.6 | Xunfeng | esp32s2-4MB | S2 variant, reversed digits |
| P7.7 | MarvelTubes | esp32s2-16MB | S2 fake MISO/CS pins, SPI 20 MHz, `rx8025t` |
| P7.8 | MarvelTubes Gen2 | esp32-16MB | no RTC, SPI 20 MHz |
| P7.9 | MarvelTubes Mini | esp32c3-4MB | `i2c_expander` CS + dimming, ST7735 80×160, USB-CDC |
| P7.10 | IPSTube S3 | esp32s3-8MB | S3 pins, CGRAM offset, no RTC |

SI HAI is not supported in v2. Each board without owner hardware is released as
"community tested" until confirmed.

## Phase 8 – New features (from v1 `TO-DO.txt`)

- [ ] **P8.1** – Change face directly with left/right; face selection first in menu.
- [ ] **P8.2** – Animated full-screen menu across all six displays.
- [ ] **P8.3** – Four-digit mode (`00:00_`, `_00:00`, blinking colon, AM/PM variants).
- [ ] **P8.4** – Date mode (switchable / timed rotation; small date digits variant).
- [ ] **P8.5** – Countdown mode (target date, rotation with clock).
- [ ] **P8.6** – Alarm: buzzer (LEDC) or light alarm, alarm indicator on display.
- [ ] **P8.7** – Info/weather tile on one digit (provider TBD, D-012).
- [ ] **P8.8** – Web UI as PWA (replaces the mobile app idea).
- [ ] **P8.9** – Face catalogue on GitHub Pages, download directly from the clock.

## v1 → v2 migration (part of release 2.0)

- [ ] **M.1** – User guide: flash once via web flasher (full image, new partition table),
  re-enter settings, convert own BMPs via web UI or `tools/etf`.
- [ ] **M.2** – Notice in the v1 README pointing to v2; v1 stays in maintenance mode.

---

## Hardware notes – IPSTube Gen1 (reference board, from v1)

| Function | GPIO / value |
|----------|--------------|
| SPI MOSI / SCLK | 32 / 33, 40 MHz, no MISO |
| DC / RST | 25 / 26 |
| CS per digit (sec-ones → hour-tens) | 15, 2, 27, 14, 12, 13 (direct GPIO, active level see v1 `DIGIT_CS_ACTIVE_LEVEL`) |
| Display enable / dimming | 4 – LEDC PWM 20 kHz, 8 bit, via Q1 transistor |
| WS2812 backlight | 5, 6 LEDs |
| Button (only one) | 0 (BOOT) |
| RTC DS1302 SCLK / IO / CE | 22 / 19 / 21 |
| Panel | ST7789 135×240 |
| Flash | 8 MB Winbond external – **DIO 40 MHz** (v1 finding, only this board; re-test in P5.9) |
| Quirks | No panel re-init after power-off (v1 `TFT_SKIP_REINIT`); GPIO2/12 are strapping pins |

## Progress log

<!-- Newest first. Date – task ID – note (measurements, surprises, follow-ups). -->

- 2026-11-26 – P0.3 – 7 variants build via `tools/build.py --all` (D-016/D-017). Default QIO 80 MHz,
  only `esp32-8MB-dio` (IPSTube Gen1) uses DIO 40 MHz. `flash_args` shows `dio` for QIO images –
  expected: the ROM loads in DIO, the 2nd-stage bootloader switches to QIO. Bootloader free space
  with offset 0x9000: esp32 QIO 0x1450 (16 %; at 0x8000 it would have been only 0x450),
  esp32 DIO 0x1AD0, s2 0x2630, s3 0x39B0, c3 0x3BB0. Changing variant/defaults files needs
  `--clean`.
- 2026-11-26 – P0.2/P0.4 – Skeleton builds for esp32, esp32s2, esp32s3, esp32c3 (separate
  `build/<target>` dirs with `-D SDKCONFIG=build/<target>/sdkconfig`). Empty app 121–150 KB.
  **Note:** esp32 bootloader has only 0xAD0 bytes (10 %) free below the 0x8000 partition-table
  offset – enabling bootloader features (rollback, verbose logs, secure boot) may require moving
  the partition table offset to 0x9000+ in P0.3. `.vscode/settings.json` is machine-specific
  (EIM path) and stays untracked. First full 4-target build takes >10 min.
- 2026-11-26 – P0.1 – ESP-IDF v6.1.1 installed via EIM (targets esp32, s2, s3, c3); activate with
  the EIM PowerShell profile script. `gh` installed, login pending (user).
- 2026-11-26 – plan created.
