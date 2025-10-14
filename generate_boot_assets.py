#!/usr/bin/env python3
"""Helper utility to regenerate boot assets for the Advantech UbiQ-480-ENWPLE.

This script ensures the `mkimage` tool from the `u-boot-tools` package is
available, installs it when necessary, and compiles the tracked `boot/boot.cmd`
into `boot/boot.scr`.

The process intentionally happens on-demand so the repository can avoid storing
binary artefacts while still providing a repeatable workflow to reproduce them.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BOOT_DIR = REPO_ROOT / "boot"
BOOT_CMD = BOOT_DIR / "boot.cmd"
BOOT_SCR = BOOT_DIR / "boot.scr"
MKIMAGE_PACKAGE = "u-boot-tools"


def run_command(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command while echoing it to stdout."""
    print("$", " ".join(cmd))
    return subprocess.run(cmd, check=check)


def ensure_mkimage() -> None:
    """Ensure the mkimage tool is present, installing it if possible."""
    if shutil.which("mkimage"):
        return

    apt_get = shutil.which("apt-get")
    if not apt_get:
        raise RuntimeError(
            "mkimage is not installed and apt-get is unavailable. "
            "Install u-boot-tools manually and re-run this script."
        )

    # Determine whether we need sudo for installation.
    if os.geteuid() == 0:
        sudo_prefix: list[str] = []
    else:
        sudo = shutil.which("sudo")
        if not sudo:
            raise RuntimeError(
                "mkimage is not installed. Run this script as root or install "
                "u-boot-tools manually."
            )
        sudo_prefix = [sudo]

    print("mkimage not found; installing {} via apt-get".format(MKIMAGE_PACKAGE))
    run_command(sudo_prefix + [apt_get, "update"])
    run_command(sudo_prefix + [apt_get, "install", "-y", MKIMAGE_PACKAGE])

    if not shutil.which("mkimage"):
        raise RuntimeError("mkimage still missing after attempted installation")


def build_boot_script() -> None:
    """Compile boot.cmd into boot.scr using mkimage."""
    if not BOOT_CMD.exists():
        raise FileNotFoundError(f"boot.cmd not found at {BOOT_CMD}")

    ensure_mkimage()
    BOOT_DIR.mkdir(parents=True, exist_ok=True)

    run_command(
        [
            "mkimage",
            "-A",
            "arm",
            "-T",
            "script",
            "-C",
            "none",
            "-n",
            "UbiQ480 Boot",
            "-d",
            str(BOOT_CMD),
            str(BOOT_SCR),
        ]
    )
    print(f"Generated {BOOT_SCR}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Regenerate boot assets for the UbiQ-480 platform")
    subparsers = parser.add_subparsers(dest="command", required=True)

    boot_parser = subparsers.add_parser(
        "boot",
        help="Compile boot.cmd into boot.scr after ensuring mkimage is installed",
    )
    boot_parser.set_defaults(func=lambda _: build_boot_script())

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
