#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Run host tests (linux target) and Python tool tests in WSL, comparable to CI.
#
# From Windows (repo root as current directory):
#     wsl -d Ubuntu-24.04 -- bash tools/wsl_test.sh [--clean]
#
# The working tree (including uncommitted changes) is mirrored into the Linux file system
# (~/dev/EleksTubeHAX2, much faster than /mnt/c) and tested there. Build output and the venv
# stay in the mirror between runs. Needs ESP-IDF in ~/esp/esp-idf (or $IDF_PATH) and rsync.
# On plain Linux/macOS run tools/host_test.py and the unittest command directly instead.

set -euo pipefail

src="$(cd "$(dirname "$0")/.." && pwd)"
dst="${ETH2_WSL_MIRROR:-$HOME/dev/EleksTubeHAX2}"
idf="${IDF_PATH:-$HOME/esp/esp-idf}"
clean=""
[[ "${1:-}" == "--clean" ]] && clean="--clean"

if [[ "$src" != "$dst" ]]; then
    mkdir -p "$dst"
    rsync -a --delete \
        --exclude /build/ --exclude /.venv/ --exclude /managed_components/ --exclude /out/ \
        --exclude __pycache__/ "$src/" "$dst/"
fi
cd "$dst"

echo "== Python tool tests"
[[ -x .venv/bin/python ]] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r tools/requirements.txt
.venv/bin/python -m unittest discover -s test/tools

echo "== Host tests (ESP-IDF linux target)"
# shellcheck disable=SC1091
. "$idf/export.sh" > /dev/null
python tools/host_test.py $clean
