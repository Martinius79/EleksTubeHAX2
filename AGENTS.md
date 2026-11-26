# AGENTS.md – EleksTubeHAX2

Rules for AI coding agents and human contributors. Plan: [docs/ROADMAP.md](docs/ROADMAP.md),
decisions: [docs/DECISIONS.md](docs/DECISIONS.md), attribution: [NOTICE.md](NOTICE.md).

## Language

- Chat responses: use the language of the user's message (or the IDE/system locale).
- Everything that is committed is **English**: code, comments, identifiers, log output, commit
  messages, documentation.

## Git

- **`main` is protected:** it only receives pull requests that the user merges. Never commit,
  push or merge to `main` yourself.
- **Feature branches** (`feature/<topic>`, `fix/<topic>`): committing and pushing there is
  allowed without asking. Check `git branch --show-current` and `git status` before every
  commit. Opening a PR is fine; merging is the user's decision.
- Do not switch branches, stash, reset, rebase, force-push, merge PRs or delete branches without
  explicit permission.
- `origin` is the project repository itself (no fork/upstream setup). PRs target `main` of `origin`.
- Every commit should build. One task ID (e.g. `P1.2`) per commit where practical; mention it in
  the commit message.

## Local-only and private values

- No machine-local or private values in tracked files: COM ports, WiFi/MQTT credentials, host
  names, IP addresses, absolute local paths. Pass ports on the command line.
- `.local/**` is git-ignored and holds machine-specific notes (port map, flash procedure).
  Read it when needed, never copy its values into tracked files.
- `.vscode/settings.json` is machine-specific (ESP-IDF extension paths) and stays untracked.

## Build, flash, test

- Activate ESP-IDF (v6.1+) first, then build via `tools/build.py` – never call `idf.py` without
  the variant's `-B`/`SDKCONFIG` (the helper does that).
- **Building is allowed, flashing is not.** `flash`, `monitor`, `erase-flash` and every
  `esptool` call happen only after an explicit user request, with the port the user names.
- **Never erase the whole flash or write from offset `0x0`** without explicit confirmation – it
  wipes settings, clock faces and any backup on the clock.
- After a change, build the affected variant(s). A full `--all` build takes ~15 min; CI builds
  every variant (P0.7).
- Host tests (P0.8, once available) must pass before committing logic changes.
- After changing `sdkconfig.defaults*` or `variants/*.sdkconfig`, rebuild with `--clean`.
- Python tools use a local venv: `python -m venv .venv` and
  `.venv/Scripts/pip install -r tools/requirements.txt` (Linux/macOS: `.venv/bin/pip`).
- Clock faces are generated (`tools/facegen`), never copied from vendor firmware or the web
  (D-018).

## Design rules

- **Never make the weakest hardware the baseline.** Defaults target capable boards; quirks (e.g.
  IPSTube Gen1 DIO 40 MHz flash) live only in that board's variant or board profile.
- Hardware is selected at runtime via board profiles (D-003) – no per-clock `#ifdef`s.
- No compile-time user configuration (D-007); settings live in NVS and are changed at runtime.
- One ESP-IDF component per feature under `components/`; `main/` only wires them together.
- Logic that does not touch hardware goes into components that build for the `linux` target and
  gets host tests.

## Documentation workflow

- Tick roadmap tasks when they are done and add a dated entry to the *Progress log* (newest
  first) with measurements, surprises and follow-ups.
- A changed decision gets a **new** D-entry; the old one is marked *superseded*, not rewritten.
- New third-party components are listed in `NOTICE.md` (name, licence, source).

## Conventions

- Line endings: LF; CRLF only for `*.cmd`, `*.bat`, `*.ps1` (see `.gitattributes`).
- Every source file starts with `SPDX-License-Identifier: GPL-3.0-or-later`.
- No wholesale reformatting, unrelated refactors or renames inside a change.
- Formatting and naming rules follow with P0.9 (`.clang-format`, `.editorconfig`).

## Files agents should not open

Binary content is not meant to be read or searched: `*.bin`, `*.bmp`, `*.png`, `*.jpg`,
`*.etf`, `*.pdf`, `*.exe`. Ask if the content is actually needed.

## Repository layout

| Path | Content |
|------|---------|
| `main/` | `app_main`, wiring of components |
| `components/` | firmware components (one per feature) |
| `variants/` | sdkconfig fragment per image variant (chip × flash size) |
| `partitions/` | partition table per flash size |
| `tools/` | build helper, encoders, generators (Python) |
| `test/host/` | host tests (`linux` target) |
| `web/` | web UI (Preact + Vite + TypeScript) |
| `docs/` | roadmap, decisions, format and API specs |

## Hardware knowledge

The predecessor [EleksTubeHAX v1](https://github.com/aly-fly/EleksTubeHAX) is the reference for
pinouts and board quirks (`include/GLOBAL_DEFINES.h`, `src/ChipSelect.cpp`, `docs/Hardware *`).
Verified v2 values are recorded in the roadmap's *Hardware notes* and later in the board profiles.
