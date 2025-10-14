#!/usr/bin/env python3
"""Project build helper.

Provides commands that produce build artifacts for the Ubiq480 project.  The
`rootfs` subcommand assembles a Debian Bookworm armel root filesystem using
`debootstrap` with QEMU user emulation.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent


def run_command(command: list[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """Run *command* with subprocess.run while echoing the invocation."""
    print(f"[build.py] $ {' '.join(command)}")
    return subprocess.run(command, check=check, **kwargs)


def require_linux() -> None:
    if platform.system() != "Linux":
        raise RuntimeError("The rootfs builder must be executed on a Linux host.")


def require_root_privileges() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("Root privileges are required to create the root filesystem.")


def ensure_command_available(command: str) -> None:
    try:
        run_command(["which", command], capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Required command '{command}' not found in PATH.") from exc


def prepare_output_directory(path: Path) -> None:
    if path.exists():
        print(f"[build.py] Removing existing directory: {path}")
        shutil.rmtree(path)
    run_command(["mkdir", "-p", str(path)])


def write_config_file(root: Path, relative_path: str, content: str) -> None:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = dedent(content).lstrip("\n")
    destination.write_text(text)
    print(f"[build.py] Wrote {destination.relative_to(root)}")


def run_rootfs(_: argparse.Namespace) -> None:
    require_linux()
    require_root_privileges()

    suite = "bookworm"
    arch = "armel"
    mirror = "http://deb.debian.org/debian"

    ensure_command_available("debootstrap")

    output_root = Path("output")
    rootfs_dir = output_root / "rootfs"

    prepare_output_directory(rootfs_dir)

    # First stage bootstrap extracts the base system.
    bootstrap_cmd = [
        "debootstrap",
        "--arch",
        arch,
        "--variant",
        "minbase",
        "--foreign",
        suite,
        str(rootfs_dir),
        mirror,
    ]

    env = os.environ.copy()
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    try:
        run_command(bootstrap_cmd, env=env)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "debootstrap failed during the extraction stage. Review the output above for details."
        ) from exc

    # Copy the QEMU static binary into the rootfs for convenience when running
    # additional configuration steps on the target.
    qemu_path = shutil.which("qemu-arm-static")
    if qemu_path:
        qemu_target_path = rootfs_dir / "usr/bin/qemu-arm-static"
        qemu_target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(qemu_path, qemu_target_path)
        print(f"[build.py] Installed emulator at {qemu_target_path.relative_to(rootfs_dir)}")
    else:
        print("[build.py] warning: qemu-arm-static not found; skipping emulator copy")

    # Install configuration snippets directly into the rootfs tree.
    write_config_file(
        rootfs_dir,
        "etc/fstab",
        """
        # <file system> <mount point> <type> <options> <dump> <pass>
        proc /proc proc defaults 0 0
        /dev/mmcblk0p1 /boot vfat defaults 0 2
        /dev/mmcblk0p2 / ext4 defaults,noatime 0 1
        """,
    )

    write_config_file(
        rootfs_dir,
        "etc/hostname",
        """
        ubiq480
        """,
    )

    write_config_file(
        rootfs_dir,
        "etc/network/interfaces.d/eth0",
        """
        auto eth0
        allow-hotplug eth0
        iface eth0 inet dhcp
        """,
    )

    write_config_file(
        rootfs_dir,
        "etc/systemd/system/serial-getty@ttyAMA0.service.d/override.conf",
        """
        [Service]
        ExecStart=
        ExecStart=-/sbin/agetty --keep-baud 115200,38400,9600 ttyAMA0 $TERM
        """,
    )

    print(f"[build.py] Root filesystem for Debian {suite} ({arch}) created at {rootfs_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build utilities for the Ubiq480 project")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rootfs_parser = subparsers.add_parser(
        "rootfs", help="Generate the Debian Bookworm armel root filesystem"
    )
    rootfs_parser.set_defaults(func=run_rootfs)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except RuntimeError as exc:
        print(f"[build.py] error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
