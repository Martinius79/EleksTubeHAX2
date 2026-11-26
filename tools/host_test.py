#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build and run the host unit tests (test/host) for the ESP-IDF "linux" target.

Works on Linux and macOS (and WSL), not on native Windows. Run inside an activated ESP-IDF
environment:

    python tools/host_test.py [--clean]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "test" / "host"
BUILD = ROOT / "build" / "host-tests"


def idf(*args: str) -> int:
    return subprocess.call(["idf.py", "-C", str(PROJECT), "-B", str(BUILD),
                            "-D", f"SDKCONFIG={BUILD / 'sdkconfig'}", *args])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clean", action="store_true", help="delete build/host-tests first")
    a = ap.parse_args()

    if sys.platform == "win32":
        print("host tests need Linux/macOS (use WSL or CI)", file=sys.stderr)
        return 2
    if a.clean and BUILD.exists():
        shutil.rmtree(BUILD)
    if not (BUILD / "sdkconfig").exists():
        # the linux target is still a preview target in some IDF versions
        if idf("set-target", "linux") and idf("--preview", "set-target", "linux"):
            return 1
    if idf("build"):
        return 1
    return subprocess.call([str(BUILD / "host_tests.elf")])


if __name__ == "__main__":
    sys.exit(main())
