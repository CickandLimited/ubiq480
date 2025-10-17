#!/usr/bin/env python3
"""Helper utility to regenerate boot assets for the Advantech UbiQ-480-ENWPLE.

This script ensures the `mkimage` tool from the `u-boot-tools` package is
available, installs it when necessary (reusing the shared build bootstrapper),
and compiles the tracked `boot/boot.cmd` into `boot/boot.scr`.

The process intentionally happens on-demand so the repository can avoid storing
binary artefacts while still providing a repeatable workflow to reproduce them.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from cli_prompts import MenuCancelled, MenuOption, prompt_for_menu_selection
from host_bootstrap import ensure_tool, set_bootstrap_enabled
from self_check import ensure_latest_checkout

REPO_ROOT = Path(__file__).resolve().parent
BOOT_DIR = REPO_ROOT / "boot"
BOOT_CMD = BOOT_DIR / "boot.cmd"
BOOT_SCR = BOOT_DIR / "boot.scr"
MKIMAGE_PACKAGE = "u-boot-tools"

LOG = logging.getLogger("ubiq480.generate_boot_assets")


def run_command(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command while echoing it to stdout."""
    print("$", " ".join(cmd))
    return subprocess.run(cmd, check=check)


def ensure_mkimage() -> None:
    """Ensure the mkimage tool is present, installing it if possible."""

    ensure_tool(
        "mkimage",
        hints={"mkimage": f"Install {MKIMAGE_PACKAGE} (provides mkimage)"},
        logger=LOG,
    )


def ensure_dependencies(_: argparse.Namespace) -> None:
    """Ensure all prerequisites for boot asset generation exist."""

    ensure_mkimage()
    LOG.info("Verified mkimage is available.")


def build_boot_script(_: argparse.Namespace) -> None:
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


ACTION_EXECUTORS = {
    "deps": ensure_dependencies,
    "boot": build_boot_script,
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Regenerate boot assets for the UbiQ-480 platform")
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Skip automatic installation of missing host dependencies.",
    )
    subparsers = parser.add_subparsers(dest="command")

    deps_parser = subparsers.add_parser(
        "deps",
        help="Ensure mkimage (from u-boot-tools) is available",
    )
    deps_parser.set_defaults(func=ensure_dependencies)

    boot_parser = subparsers.add_parser(
        "boot",
        help="Compile boot.cmd into boot.scr after ensuring mkimage is installed",
    )
    boot_parser.set_defaults(func=build_boot_script)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    ensure_latest_checkout(REPO_ROOT, logger=LOG)
    set_bootstrap_enabled(not args.no_bootstrap)

    if args.command:
        actions = [args.command]
    else:
        options = [
            MenuOption("deps", "Ensure mkimage is installed"),
            MenuOption("boot", "Compile boot.cmd into boot.scr"),
        ]
        try:
            actions = prompt_for_menu_selection(
                "Select one or more boot asset tasks to run:",
                options,
                allow_multiple=True,
                print_func=LOG.info,
            )
        except MenuCancelled:
            LOG.info("No boot asset tasks selected; exiting.")
            return 1

        if not actions:
            LOG.info("No boot asset tasks selected; exiting.")
            return 1

    try:
        for action in actions:
            ACTION_EXECUTORS[action](args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
