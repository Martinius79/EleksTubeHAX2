# EleksTubeHAX2 – Roadmap

Living work plan for the ESP-IDF rewrite. Work through it top to bottom; tick boxes as tasks are
finished and note anything surprising under *Progress log*. Architecture decisions live in
[DECISIONS.md](DECISIONS.md) – change a decision there first, then update this plan.

**Current focus:** Phase 2 – board abstraction & display
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
- [x] **P0.5** – Licence & attribution: GPL-3.0 kept, `NOTICE.md` naming SmittyHalibut,
  aly-fly and all EleksTubeHAX contributors; SPDX headers in source files.
- [x] **P0.6** – `AGENTS.md` / contributor rules (language, git rules, build vs. flash policy).
- [x] **P0.7** – CI (GitHub Actions, `espressif/esp-idf-ci-action`): build matrix of all
  variants, host tests (P0.8), web UI build (P4.6). Artifacts per variant.
- [x] **P0.8** – Host test harness: components built for the `linux` target with Unity,
  run by `idf.py --preview set-target linux` + `ctest`/test runner in CI.
  *Done when* one dummy test runs locally and in CI. (Local: WSL via `tools/wsl_test.sh`.)
- [x] **P0.9** – Coding style: `.clang-format`, `.editorconfig`; naming conventions in AGENTS.md.

## Phase 1 – Clock-face image format (`.etf`) 

- [x] **P1.1** – Write the format spec `docs/FORMAT_ETF.md`: header (magic, version, w/h,
  glyph count, glyph table with offsets), encodings `RAW565`, `RLE565`, `PAL8_RLE`,
  `DEFLATE565`, `DEFLATE_PAL8` (D-020), per-glyph encoding, glyph codes = Unicode code points.
  Glyphs 0–9 required; optional `:`, blank, AM/PM, icons.
- [x] **P1.2** – C decoder component `components/etf`: streaming, line by line into a caller
  buffer (no full frame needed), bounds-checked against corrupt files. Inflate via ROM `tinfl`
  on target; the `linux` host build has no ROM → vendored miniz `tinfl` (MIT) behind the same
  small interface. Verify `esp_rom_crc32_le` against the zlib CRC test vector.
- [x] **P1.3** – Python encoder `tools/etf/` (Pillow): resize, quantise, choose the smallest
  encoding automatically, CLI `etf encode <dir|images> -o face.etf --size 135x240`.
- [x] **P1.4** – Test images (solid, gradient, noise, >256 colours, exactly 256 colours, 1px
  details) generated deterministically in `test/tools/test_etf.py` – no binary files in git.
  Golden `.etf` fixtures for the C decoder are produced from them in P1.2. Transparency
  (`HAS_KEY`) is specified but not yet produced by the encoder.
- [x] **P1.5** – Host tests: round trip encoder→decoder pixel-exact (lossless modes),
  corrupt/truncated file handling, size budget report per encoding.
- [x] **P1.6** – Encode the generated faces (P1.7) to `.etf` in both sizes (135×240, 80×160);
  record sizes per encoding in the progress log. v1 faces are not shipped (D-018).
  *Done when* the built-in faces fit and the smallest-encoding choice is documented.
- [ ] **P1.7** – Clock-face generator `tools/facegen`: procedural styles rendered from geometry
  only (no source images), parameters for colour, stroke width, size, digit shapes.
  Styles `nixie` (glowing wire, hex anode mesh, unlit cathodes) and `minimal` (flat amber,
  embedded fallback) exist; `facegen.py build` renders and encodes all built-in faces.
  Next: more styles (7-segment, VFD, neon, flat/minimal), optional font-based digits (only fonts
  with a free licence), direct `.etf` output, later the same generator in the web UI (P4.7).
  Generated images are CC0-1.0 (D-019).

## Phase 2 – Board abstraction & display 🔌

- [x] **P2.1** – `components/board`: profile struct (chip, display type/size/offsets/colour
  order/inversion, SPI pins + freq, CS backend + pins, enable/dimming pin + mode, LED pin/count,
  input type + pins, RTC type + pins, buzzer, digit order). Profiles as const table.
- [x] **P2.2** – Profile `ipstube_gen1` from v1 data (see *Hardware notes*).
- [x] **P2.3** – Profile selection: NVS key `board.profile`; compile-time default per variant
  (`CONFIG_BOARD_DEFAULT_ID`); API `board_save_id()`. Console command `board set <id>` → P4.4.
- [x] **P2.4** – `components/display`: `esp_lcd` SPI panel IO, ST7789 driver, init of all six
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
- [ ] **P4.4** – `esp_console` CLI over UART/USB-CDC: `wifi`, `board list/set` (P2.3), `config get/set`,
  `face`, `reboot`, `bench` (v1 TODO "config via serial terminal").
- [ ] **P4.5** – REST API (`esp_http_server`): `/api/status`, `/api/config` (GET/PATCH),
  `/api/faces` (list/upload/delete/select), `/api/wifi`, `/api/ota`, `/api/system`.
  Spec in `docs/API.md` (OpenAPI optional). Auth: optional password (D-011, open).
- [ ] **P4.6** – Web UI `web/` (Preact + Vite + TypeScript), responsive, gzip, served from a
  dedicated partition or embedded; built in CI.
- [ ] **P4.7** – Face upload in the browser: canvas resize to the device size, JS `.etf`
  encoder (decodes pixel-identical to Python; byte identity is impossible because DEFLATE
  output differs between zlib implementations), validated against `test/host/fixtures` in CI,
  preview, upload.
- [ ] **P4.8** – Face storage management on LittleFS: quota, delete, at least one face always
  present (fallback `minimal` is already embedded, D-021); ship `nixie-glow` in the initial
  storage image.
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

- 2026-11-27 – P1.7 (round 2) – Style `in14`: round tube seen from the front (glass with
  shoulder and exhaust tip, mica disc, support rods, coarse honeycomb anode in front of the
  digit, broad red-orange glow without white core, pins, optional underlight – preset
  `in14-violet` after a photo of a real IN-14 clock). Soviet glyph set: flat-top 3, 5 as an
  upside-down 2 and 9 as an upside-down 6 like the real tube (`soviet_5=false` for a normal 5).
  Nixie: support rods, out-of-focus cathode stack, glass highlights. Sizes at 135×240: in14
  164 KB, in14-violet 184 KB, nixie-glow 262 KB.
- 2026-11-27 – P1.7 (round 1) – Presets + `--set key=value` overrides; new styles `sevenseg`
  (LED, LCD), `vfd`, `varisymbol` (14-segment gas discharge in the manner of the Telefunken
  Varisymbol: frame with unsplit top/bottom, centre cross, four diagonals; digit mapping taken
  from reference pictures, rendering original), `neon` (tube with electrodes at open ends only,
  shadow on a textured wall). Sizes at 135×240: minimal 16 KB, LCD 18 KB, 7-seg LED 52–68 KB,
  varisymbol 92 KB, VFD 108 KB, neon 116 KB, nixie 252 KB. Next: nixie realism, round
  IN-14-style tube and a Soviet-style glyph set (5 = rotated 2).
- 2026-11-26 – P2.4 – `components/display`: SPI via `esp_lcd_panel_io` without hardware CS
  (6 panels exceed the CS lines of the SPI peripheral; the other clocks use 74HC595 / I2C
  expanders anyway), CS backend `gpio` (hc595 / i2c expander → Phase 7), own ST7789 init
  ported byte by byte from v1 (the IDF ST7789 driver only sends a minimal init without
  gamma/VCOM/porch), shared reset, panel power via the enable pin (on/off; PWM in P2.8),
  streaming API `display_area_begin/write/end` that blocks until each DMA transfer is done.
  `panel.c` (init sequence, window + offsets) is host-tested with a recording mock (6 tests).
  `main/display_test.c` prepares P2.5/P2.6: colour per digit, then digit index from the
  fallback face with draw timing. Not yet run on hardware.
- 2026-11-26 – P2.1–P2.3 – `components/board`: profile struct (panel, SPI, CS backend, dimming,
  LEDs, input, RTC, buzzer, digit order), table with `ipstube_gen1`, validation (pin exists on
  the chip, not a flash pin, no input-only pin as output, no pin used twice except shared I2C
  bus lines), selection stored id → build default → none (display untouched). v1 details: Gen1
  panels run without CGRAM offset and with RGB order, while EleksTube/IPSTube S3 use offset
  (52, 40) and BGR – TFT_eSPI couples CGRAM_OFFSET to BGR; ST7789 uses SPI mode 3. To verify on
  hardware in P2.5. Boards without Q1 transistor (no hardware dimming) and the optional LED
  stripe (34 LEDs) become runtime options (P2.8 / P3.4), not separate profiles.
- 2026-11-26 – P1.6 – Built-in faces (11 glyphs: 0–9 + blank), totals per encoding:

  | Face | Size | RAW565 | RLE565 | PAL8_RLE | DEFLATE565 | DEFLATE_PAL8 | .etf |
  |---|---|---|---|---|---|---|---|
  | nixie-glow | 135×240 | 680 KB | 520 KB | n/a | 254 KB | n/a | **252 KB** |
  | nixie-glow | 80×160 | 270 KB | 239 KB | n/a | 126 KB | n/a | **125 KB** |
  | minimal | 135×240 | 398 KB | 52 KB | 34 KB | 21 KB | 16 KB | **16 KB** |
  | minimal | 80×160 | 168 KB | 36 KB | 23 KB | 13 KB | 10 KB | **11 KB** |

  Smallest encoding: DEFLATE565 for photo-like faces, DEFLATE_PAL8 for flat faces (anti-aliased
  edges of one hue stay below 256 colours). `minimal` embedded as fallback (D-021, app +30 KB);
  `app_main` verifies and decodes it at boot and logs timing. `tinfl_decompress` links from ROM
  on esp32 (0x4005ef30) and esp32c3 (0x400000f4). etf API: work buffer no longer needs 8-byte
  alignment (decoder aligns itself). Digit 5 stem now runs straight into the bowl (kink visible
  with thick strokes).
- 2026-11-26 – P1.2 – `components/etf`: parser + streaming row decoder for all 5 encodings,
  memory and FILE sources, work buffer 256 B (+512 B palette, +~11 KB tinfl state + 4 KB dict
  for DEFLATE). Host build uses miniz 1.14 `tinfl` (public domain) against the ROM header; that
  header hardcodes Xtensa options and redefines them on x86 → included as SYSTEM dir on linux.
  Shared fixtures `test/host/fixtures` (24 cases, 116 KB) from `generate.py`; Python and C must
  classify them identically and decode to the same `.expect` pixels. Mutation check showed that
  a disabled row-bounds check still "passed" (overflow, then the expected error) → host tests
  now run with ASan + UBSan (alignment check off: miniz.h enables unaligned loads only on x86).
  CPython on Windows ships zlib-ng 2.2.4, Linux zlib 1.3: DEFLATE bytes differ, so fixture
  freshness is checked on decoded content, and P4.7 parity is defined on pixels.
- 2026-11-26 – P0.8 – Local tests via WSL Ubuntu 24.04 (same base as the CI container) with
  ESP-IDF v6.1.1 in `~/esp/esp-idf`. `tools/wsl_test.sh` rsyncs the Windows working tree to
  `~/dev/EleksTubeHAX2` and runs Python + host tests: first run 23 s, incremental 9 s (Python
  tests 5.8 s vs. 15 s on native Windows). The ESP-IDF clone needed `http.version=HTTP/1.1`
  after an HTTP/2 stream abort.
- 2026-11-26 – P1.3–P1.5 – `tools/etf/etf.py` (encode/info/decode + reference decoder), 15 unit
  tests in `test/tools` (round trip per encoding, RLE row boundaries, 4 KB DEFLATE window, byte
  order, truncation, bit flips, fuzzed pixel streams; ~15 s). Tests found three spec/impl gaps:
  glyph table was not CRC-protected (→ `header_crc` now covers header + table + metadata),
  zlib errors leaked, trailing padding hid truncation. Nixie face 135×240 encodes to 241 KB,
  all glyphs DEFLATE565, cropping trims uniform borders automatically. CI now encodes the
  nixie face in both sizes as artifact.
- 2026-11-26 – P1.1 – `docs/FORMAT_ETF.md` v1.0. Size estimate on the generated nixie face
  (135×240, 10 glyphs, 830 colours in glyph 0): RAW565 633 KB, RLE565 525 KB, PAL8 (lossy)
  321 KB, PAL8_RLE 303 KB, DEFLATE565 lossless 321/258/240/232 KB at window 512 B/1 KB/4 KB/
  32 KB, DEFLATE_PAL8 220 KB. Byte-plane splitting made DEFLATE worse (275 KB). → D-020: add
  DEFLATE encodings with 4 KB window, drop QOI. 4 MB variant storage (896 KB) holds ~3 nixie
  sets; flat faces are much smaller.
- 2026-11-26 – P0.7 – GitHub ruleset "main protection" active: PR required (0 approvals), required
  check `CI ok` (aggregate job over firmware, host tests, tools), no force-push / deletion, no
  bypass. CI container `espressif/idf:v6.1.1` is Ubuntu 24.04 → local WSL should use
  Ubuntu 24.04 for comparable host tests. Work continues on `feature/phase1-etf`.
- 2026-11-26 – P0.7/P0.8/P0.9 – CI green: 7 variants in the `espressif/idf:v6.1.1` container
  (~2.5 min each, parallel), artifacts with merged binary per variant, host tests, clang-format
  check (pinned 21.1.8 via pip), nixie faces as artifact. The ESP-IDF `linux` target is still
  *preview* in v6.1.1 (`tools/host_test.py` falls back to `--preview`). Host tests cannot run on
  native Windows; this machine has no WSL yet. Actions bumped to checkout/setup-python/
  upload-artifact v7 (Node 20 deprecation). GitHub `main` has no branch protection yet.
- 2026-11-26 – P1.7 (started) – v1 nixie face is very likely a stock photo (identical faces in all
  vendor firmwares) → D-018: no v1 faces. Prototype `tools/facegen/nixie.py` renders an own
  nixie set at 135×240 in <1 s (4× supersampling, layered Gaussian glow, red gas fill, hex mesh,
  dim unlit cathodes). Python deps in `tools/requirements.txt`, local `.venv`.
- 2026-11-26 – P0.6 – `AGENTS.md` adapted from v1: commit only on request and on feature
  branches, build yes / flash only on request, no local values in tracked files (`.local/`),
  weakest board never the baseline, roadmap/decision workflow. v1 fork/upstream rules dropped
  (v2 is its own repository).
- 2026-11-26 – P0.5 – `NOTICE.md` with origin projects and v1 contributors (from v1 git history
  and README §9), README with build + credits. Licence identifier `GPL-3.0-or-later` (v1 only
  ships the GPL-3.0 text, no "only/or later" statement). Origin/licence of the v1 clock-face
  graphics is unknown – added as acceptance criterion to P1.6.
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
