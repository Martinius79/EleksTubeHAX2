#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build one or more firmware image variants (chip x flash size, see docs/DECISIONS.md D-004).

Each variant is defined by variants/<variant>.sdkconfig; the chip target is the name prefix
before the first '-'. Every variant gets its own build dir and sdkconfig: build/<variant>/.

Run inside an activated ESP-IDF environment:
    python tools/build.py --list
    python tools/build.py esp32-4MB                    # build
    python tools/build.py --all --clean                # fresh build of every variant
    python tools/build.py esp32-8MB-dio -- -p COM5 flash monitor
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VARIANT_DIR = ROOT / "variants"


def variants() -> list[str]:
    return sorted(p.stem for p in VARIANT_DIR.glob("*.sdkconfig"))


def run_variant(variant: str, clean: bool, idf_args: list[str]) -> int:
    target = variant.split("-", 1)[0]
    build_dir = ROOT / "build" / variant
    if clean and build_dir.exists():
        shutil.rmtree(build_dir)

    defaults = f"sdkconfig.defaults;variants/{variant}.sdkconfig"
    base = [
        "idf.py",
        "-C", str(ROOT),
        "-B", str(build_dir),
        "-D", f"SDKCONFIG={build_dir / 'sdkconfig'}",
        "-D", f"SDKCONFIG_DEFAULTS={defaults}",
    ]
    # set-target only on a fresh build dir; it would otherwise discard the sdkconfig.
    if not (build_dir / "sdkconfig").exists():
        rc = subprocess.call(base + ["set-target", target], shell=sys.platform == "win32")
        if rc:
            return rc
    return subprocess.call(base + (idf_args or ["build"]), shell=sys.platform == "win32")


def main() -> int:
    argv = sys.argv[1:]
    idf_args: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, idf_args = argv[:split], argv[split + 1:]

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("variant", nargs="*", help="variant name(s), see --list")
    parser.add_argument("--all", action="store_true", help="build every variant")
    parser.add_argument("--clean", action="store_true", help="delete build/<variant> first "
                        "(needed after changing sdkconfig.defaults or variant files)")
    parser.add_argument("--list", action="store_true", help="list variants and exit")
    args = parser.parse_args(argv)

    known = variants()
    if args.list:
        print("\n".join(known))
        return 0
    selected = known if args.all else args.variant
    if not selected:
        parser.error("give a variant, --all or --list")
    unknown = [v for v in selected if v not in known]
    if unknown:
        parser.error(f"unknown variant(s): {', '.join(unknown)} (known: {', '.join(known)})")

    results = {v: run_variant(v, args.clean, idf_args) for v in selected}
    if len(results) > 1:
        print("\nSummary:")
        for v, rc in results.items():
            print(f"  {v:16} {'ok' if rc == 0 else f'FAILED ({rc})'}")
    return max(results.values())


if __name__ == "__main__":
    sys.exit(main())
