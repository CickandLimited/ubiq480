#!/usr/bin/env python3
"""Project build helper for the Ubiq480 platform.

This script orchestrates every build stage required to assemble a complete
microSD image for the Advantech UbiQ-480-ENWPLE.  Each major step of the
pipeline is exposed as a sub-command:

* ``deps``  – verify required host tooling is available.
* ``uboot`` – clone and build the U-Boot bootloader.
* ``kernel`` – clone and build the Linux kernel image.
* ``dtb`` – compile the Ubiq480-specific device tree.
* ``boot`` – generate the binary boot script using ``mkimage``.
* ``rootfs`` – assemble the Debian Bookworm root filesystem via ``debootstrap``.
* ``image`` – build the final microSD card image by combining the previous
  artefacts.
* ``all`` – execute the entire workflow sequentially.

The helper keeps source checkouts inside ``output/cache`` to avoid polluting the
repository and logs all console output to ``output/build.log`` for later
inspection.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Callable

from progress import ProgressUpdate, format_progress_message, get_progress_parser

LOG = logging.getLogger("ubiq480.build")

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = REPO_ROOT / "output"
CACHE_DIR = OUTPUT_DIR / "cache"

DEFAULT_SHALLOW_DEPTH = 64
MIN_FREE_DISK_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB

UBOOT_REPO = "https://source.denx.de/u-boot/u-boot.git"
UBOOT_REF = "v2016.09"
UBOOT_CONFIG = "mx31ads_config"

KERNEL_REPO = "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git"
KERNEL_REF = "v5.10.217"
KERNEL_DEFCONFIG = "imx_v6_v7_defconfig"
DTB_TARGET = "arch/arm/boot/dts/imx31-ubiq480-g070vw01.dtb"

BOOT_CMD = REPO_ROOT / "boot" / "boot.cmd"
BOOT_SCR = OUTPUT_DIR / "boot.scr"

ROOTFS_SUITE = "bookworm"
ROOTFS_ARCH = "armel"
ROOTFS_MIRROR = "http://deb.debian.org/debian"

IMAGE_SIZE_MB = 2048
BOOT_PARTITION_SIZE_MB = 64
BOOT_LABEL = "UBIQBOOT"
ROOT_LABEL = "ubiq480-root"

DEPENDENCY_HINTS: dict[str, str] = {
    "git": "sudo apt-get install git",
    "make": "sudo apt-get install build-essential",
    "arm-linux-gnueabi-gcc": "sudo apt-get install gcc-arm-linux-gnueabi",
    "arm-linux-gnueabi-ld": "sudo apt-get install binutils-arm-linux-gnueabi",
    "debootstrap": "sudo apt-get install debootstrap",
    "losetup": "sudo apt-get install util-linux",
    "sfdisk": "sudo apt-get install fdisk",
    "mkfs.vfat": "sudo apt-get install dosfstools",
    "mkfs.ext4": "sudo apt-get install e2fsprogs",
    "mkimage": "sudo apt-get install u-boot-tools",
    "truncate": "sudo apt-get install coreutils",
    "mount": "sudo apt-get install mount",
    "umount": "sudo apt-get install mount",
}

ALL_DEPENDENCIES = [
    "git",
    "make",
    "arm-linux-gnueabi-gcc",
    "arm-linux-gnueabi-ld",
    "debootstrap",
    "mkimage",
    "losetup",
    "sfdisk",
    "mkfs.vfat",
    "mkfs.ext4",
    "truncate",
    "mount",
    "umount",
]


@dataclass(frozen=True)
class StageArtefact:
    """Description of an artefact fetched or produced by a build stage."""

    identifier: str
    kind: str
    description: str
    estimated_size_mb: int | None = None
    notes: str | None = None


PIPELINE_ORDER = ["deps", "uboot", "kernel", "dtb", "boot", "rootfs", "image"]

STAGE_ARTEFACTS: dict[str, list[StageArtefact]] = {
    "deps": [],
    "uboot": [
        StageArtefact(
            identifier="repo:u-boot",
            kind="Git repository",
            description="U-Boot source (depth 64 clone from source.denx.de)",
            estimated_size_mb=200,
            notes="Cached under output/cache/u-boot/ for reuse.",
        ),
        StageArtefact(
            identifier="output:u-boot.bin",
            kind="Build artefact",
            description="u-boot.bin bootloader image",
            estimated_size_mb=1,
        ),
    ],
    "kernel": [
        StageArtefact(
            identifier="repo:linux",
            kind="Git repository",
            description="Linux kernel source (depth 64 clone from kernel.org)",
            estimated_size_mb=1800,
            notes="Shared with the dtb stage when run separately.",
        ),
        StageArtefact(
            identifier="output:zImage",
            kind="Build artefact",
            description="zImage kernel binary",
            estimated_size_mb=20,
        ),
    ],
    "dtb": [
        StageArtefact(
            identifier="repo:linux",
            kind="Git repository",
            description="Linux kernel source (depth 64 clone from kernel.org)",
            estimated_size_mb=1800,
            notes="Reused if the kernel stage has already populated the cache.",
        ),
        StageArtefact(
            identifier="output:dtb",
            kind="Build artefact",
            description="imx31-ubiq480-g070vw01.dtb device tree blob",
            estimated_size_mb=1,
        ),
    ],
    "boot": [
        StageArtefact(
            identifier="output:boot.scr",
            kind="Build artefact",
            description="boot.scr compiled boot script",
            estimated_size_mb=1,
        ),
    ],
    "rootfs": [
        StageArtefact(
            identifier="packages:debootstrap",
            kind="Package download",
            description="Debootstrap base system packages from deb.debian.org",
            estimated_size_mb=600,
            notes="Written into output/rootfs/",
        ),
        StageArtefact(
            identifier="output:rootfs",
            kind="Filesystem tree",
            description="Staged Debian Bookworm root filesystem",
            estimated_size_mb=1200,
        ),
    ],
    "image": [
        StageArtefact(
            identifier="output:ubiq480.img",
            kind="Disk image",
            description="Bootable microSD card image",
            estimated_size_mb=IMAGE_SIZE_MB,
        ),
    ],
}


def format_size(estimated_mb: int | None) -> str:
    """Return a human-readable approximation for *estimated_mb*."""

    if estimated_mb is None:
        return "unknown size"
    if estimated_mb >= 1024:
        gib = estimated_mb / 1024
        return f"~{gib:.1f} GiB ({estimated_mb} MiB)"
    return f"~{estimated_mb} MiB"


def collect_stage_artefacts(command: str) -> list[StageArtefact]:
    """Return artefacts associated with *command* (deduplicated for ``all``)."""

    if command == "all":
        seen: dict[str, StageArtefact] = {}
        for stage in PIPELINE_ORDER:
            for artefact in STAGE_ARTEFACTS.get(stage, []):
                seen.setdefault(artefact.identifier, artefact)
        return list(seen.values())
    return list(STAGE_ARTEFACTS.get(command, []))


def log_stage_summary(command: str) -> None:
    """Emit a human-readable summary of artefacts for *command*."""

    artefacts = collect_stage_artefacts(command)
    stage_label = "full pipeline" if command == "all" else f"'{command}' stage"

    LOG.info("Planned artefacts for the %s:", stage_label)
    if not artefacts:
        LOG.info("  (no downloads or large artefacts expected)")
        return

    total_known_mb = 0
    has_unknown = False
    for artefact in artefacts:
        size_text = format_size(artefact.estimated_size_mb)
        LOG.info("  - %s (%s, %s)", artefact.description, artefact.kind, size_text)
        if artefact.notes:
            LOG.info("      %s", artefact.notes)
        if artefact.estimated_size_mb is None:
            has_unknown = True
        else:
            total_known_mb += artefact.estimated_size_mb

    if has_unknown and total_known_mb:
        LOG.info(
            "Estimated total size: at least %s (additional components have unknown size)",
            format_size(total_known_mb),
        )
    elif has_unknown:
        LOG.info("Estimated total size: unknown")
    else:
        LOG.info("Estimated total size: %s", format_size(total_known_mb))


def confirm_execution(command: str, *, assume_yes: bool) -> bool:
    """Display artefact summary and request confirmation for *command*."""

    log_stage_summary(command)
    if assume_yes:
        LOG.info("Proceeding without interactive confirmation because --yes was supplied.")
        return True

    stage_label = "full pipeline" if command == "all" else f"'{command}' stage"
    prompt = f"Proceed with the {stage_label}? [y/N]: "
    try:
        response = input(prompt)
    except (EOFError, KeyboardInterrupt):
        LOG.info("No confirmation received; aborting execution.")
        return False

    if response.strip().lower() not in {"y", "yes"}:
        LOG.info("User declined to continue (responded with '%s').", response.strip())
        return False
    return True


@dataclass
class CommandResult:
    """Light-weight wrapper representing the output of ``run_command``."""

    args: list[str]
    returncode: int
    output: str = ""


def setup_logging() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / "build.log"

    LOG.setLevel(logging.INFO)
    LOG.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_path, mode="w")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    LOG.addHandler(file_handler)
    LOG.addHandler(console_handler)


def run_command(
    command: list[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    input_text: str | None = None,
) -> CommandResult:
    """Run *command* while mirroring stdout to the logger and console."""

    parser, prepared_command = get_progress_parser(list(command))
    LOG.info("$ %s", " ".join(prepared_command))

    output_lines: list[str] = []

    def emit_line(message: str, *, console: str | None = None) -> None:
        LOG.info(message)
        print(console if console is not None else message, flush=True)
        output_lines.append(message + "\n")

    def emit_progress(update: ProgressUpdate) -> None:
        emit_line(format_progress_message(update))

    download_returncode = _maybe_run_python_download(
        prepared_command,
        cwd=cwd,
        emit_line=emit_line,
        emit_progress=emit_progress,
        capture_output=capture_output,
        input_text=input_text,
    )
    if download_returncode is not None:
        if check and download_returncode != 0:
            raise subprocess.CalledProcessError(
                download_returncode,
                prepared_command,
                output="".join(output_lines),
            )
        return CommandResult(prepared_command, download_returncode, "".join(output_lines))

    if capture_output:
        completed = subprocess.run(
            prepared_command,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if completed.stdout:
            for segment in _iter_output_segments(completed.stdout):
                handled = False
                if parser:
                    updates = parser.parse(segment)
                    if updates:
                        handled = True
                        for update in updates:
                            emit_progress(update)
                if not handled:
                    emit_line(segment.rstrip(), console=segment)
        if check and completed.returncode != 0:
            raise subprocess.CalledProcessError(
                completed.returncode,
                prepared_command,
                output="".join(output_lines),
            )
        return CommandResult(prepared_command, completed.returncode, "".join(output_lines))

    process = subprocess.Popen(
        prepared_command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert process.stdout is not None  # For type-checkers.

    for raw_line in process.stdout:
        for segment in _iter_output_segments(raw_line):
            handled = False
            if parser:
                updates = parser.parse(segment)
                if updates:
                    handled = True
                    for update in updates:
                        emit_progress(update)
            if not handled:
                emit_line(segment.rstrip(), console=segment)

    process.stdout.close()
    returncode = process.wait()
    if check and returncode != 0:
        raise subprocess.CalledProcessError(returncode, prepared_command, output="".join(output_lines))

    return CommandResult(prepared_command, returncode, "".join(output_lines))


def require_linux() -> None:
    if platform.system() != "Linux":
        raise RuntimeError("The rootfs builder must be executed on a Linux host.")


def require_root_privileges() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("Root privileges are required to create the root filesystem.")


def ensure_command_available(command: str) -> None:
    if shutil.which(command) is None:
        hint = DEPENDENCY_HINTS.get(command)
        message = f"Required command '{command}' not found in PATH."
        if hint:
            message = f"{message} Try: {hint}"
        raise RuntimeError(message)


def _iter_output_segments(text: str) -> list[str]:
    """Return sanitized output *text* split into logical display segments."""

    if not text:
        return []
    return text.replace("\r", "\n").splitlines()


def _maybe_run_python_download(
    command: list[str],
    *,
    cwd: Path | None,
    emit_line: Callable[[str], None],
    emit_progress: Callable[[ProgressUpdate], None],
    capture_output: bool,
    input_text: str | None,
) -> int | None:
    """Intercept download commands lacking native progress support."""

    if capture_output or input_text is not None or not command:
        return None

    parsed = _parse_download_command(command)
    if not parsed:
        return None

    url, output = parsed
    destination = Path(output)
    if not destination.is_absolute():
        base_dir = cwd if cwd is not None else Path.cwd()
        destination = base_dir / destination

    emit_line(f"Downloading {url} -> {destination}")
    try:
        return_code = _download_with_progress(url, destination, emit_progress)
    except Exception as exc:  # noqa: BLE001
        emit_line(f"Download failed: {exc}")
        return 1

    emit_line(f"Download complete: {destination}")
    return return_code


def _parse_download_command(command: list[str]) -> tuple[str, str] | None:
    """Return ``(url, output_path)`` if *command* resembles curl/wget usage."""

    program = Path(command[0]).name
    args = command[1:]
    url: str | None = None
    output: str | None = None

    if program == "curl":
        iterator = iter(args)
        for token in iterator:
            if token in {"-L", "--location", "-s", "--silent"}:
                continue
            if token in {"-o", "--output"}:
                output = next(iterator, None)
                continue
            if token.startswith("--output="):
                output = token.split("=", 1)[1]
                continue
            if token.startswith("-"):
                continue
            if url is None:
                url = token
        if url and output is None:
            path = urllib.parse.urlparse(url).path
            output = Path(path).name or "download"
    elif program == "wget":
        iterator = iter(args)
        for token in iterator:
            if token in {"-O", "--output-document"}:
                output = next(iterator, None)
                continue
            if token.startswith("--output-document="):
                output = token.split("=", 1)[1]
                continue
            if token.startswith("-"):
                continue
            if url is None:
                url = token
        if url and output is None:
            path = urllib.parse.urlparse(url).path
            output = Path(path).name or "download"
    else:
        return None

    if url and output:
        return url, output
    return None


def _download_with_progress(
    url: str,
    destination: Path,
    emit_progress: Callable[[ProgressUpdate], None],
) -> int:
    """Download *url* to *destination* while emitting progress updates."""

    destination.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.monotonic()
    downloaded = 0
    last_report_time = start_time
    last_percent: int | None = None

    with contextlib.closing(urllib.request.urlopen(url)) as response:
        total_header = response.getheader("Content-Length")
        try:
            total_bytes = int(total_header) if total_header is not None else None
        except (TypeError, ValueError):  # pragma: no cover - defensive
            total_bytes = None
        chunk_size = 64 * 1024
        with destination.open("wb") as file_obj:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                file_obj.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                percent = None
                if total_bytes:
                    percent = (downloaded / total_bytes) * 100
                elapsed = max(now - start_time, 1e-6)
                speed = downloaded / elapsed
                should_emit = False
                if percent is not None:
                    percent_int = int(percent)
                    if percent_int != last_percent or now - last_report_time >= 1.0:
                        last_percent = percent_int
                        should_emit = True
                elif now - last_report_time >= 1.0:
                    should_emit = True
                if should_emit:
                    emit_progress(
                        ProgressUpdate(
                            label="download",
                            percent=percent,
                            size_bytes=downloaded,
                            total_size_bytes=total_bytes,
                            speed_bytes_per_sec=speed,
                        )
                    )
                    last_report_time = now

    elapsed_total = max(time.monotonic() - start_time, 1e-6)
    emit_progress(
        ProgressUpdate(
            label="download",
            percent=100.0 if downloaded and total_bytes else None,
            size_bytes=downloaded,
            total_size_bytes=total_bytes,
            speed_bytes_per_sec=downloaded / elapsed_total if downloaded else None,
        )
    )
    return 0


def _ensure_sufficient_disk_space(path: Path, *, required_bytes: int = MIN_FREE_DISK_BYTES) -> None:
    """Validate that *path* has at least *required_bytes* of free space."""

    usage = shutil.disk_usage(path)
    if usage.free < required_bytes:
        required_gib = required_bytes / (1024**3)
        available_gib = usage.free / (1024**3)
        message = (
            f"Insufficient disk space in {path}. "
            f"{available_gib:.2f} GiB available but {required_gib:.2f} GiB required. "
            "Free disk space or move the cache directory before retrying."
        )
        LOG.error(message)
        raise RuntimeError(message)


def _ref_exists(path: Path, ref: str) -> bool:
    """Return ``True`` if *ref* is available inside the git repository at *path*."""

    result = run_command(
        ["git", "rev-parse", "--verify", ref],
        cwd=path,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def ensure_repo(url: str, destination: Path, ref: str | None = None) -> Path:
    """Ensure a shallow clone of *url* exists at *destination* and contains *ref*."""

    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ensure_sufficient_disk_space(destination.parent)
        clone_cmd = ["git", "clone", "--depth", str(DEFAULT_SHALLOW_DEPTH)]
        if ref:
            clone_cmd.extend(["--branch", ref, "--single-branch"])
        clone_cmd.extend([url, str(destination)])
        LOG.info("Cloning %s into %s with depth %s", url, destination, DEFAULT_SHALLOW_DEPTH)
        run_command(clone_cmd)
        return destination

    if ref and _ref_exists(destination, ref):
        LOG.info("Reusing cached repository %s for ref %s", destination, ref)
        return destination

    _ensure_sufficient_disk_space(destination)
    LOG.info(
        "Updating cached repository %s with shallow fetch (depth %s)",
        destination,
        DEFAULT_SHALLOW_DEPTH,
    )
    fetch_cmd = [
        "git",
        "fetch",
        "--prune",
        "--tags",
        "--depth",
        str(DEFAULT_SHALLOW_DEPTH),
        "origin",
    ]
    run_command(fetch_cmd, cwd=destination)
    return destination


def prepare_output_directory(path: Path) -> None:
    if path.exists():
        LOG.info("Removing existing directory: %s", path)
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_config_file(root: Path, relative_path: str, content: str) -> None:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = dedent(content).lstrip("\n")
    destination.write_text(text)
    LOG.info("Wrote %s", destination.relative_to(root))


def find_missing_commands(commands: list[str]) -> list[str]:
    return [cmd for cmd in commands if shutil.which(cmd) is None]


def configure_toolchain_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("ARCH", "arm")
    env.setdefault("CROSS_COMPILE", "arm-linux-gnueabi-")
    return env


def checkout_ref(path: Path, ref: str) -> None:
    run_command(["git", "checkout", "--force", ref], cwd=path)
    run_command(["git", "reset", "--hard", ref], cwd=path)
    run_command(["git", "clean", "-fdx"], cwd=path)


def build_uboot(_: argparse.Namespace) -> None:
    ensure_command_available("git")
    ensure_command_available("make")
    env = configure_toolchain_env()
    env["KCFLAGS"] = "-march=armv5te"

    repo_path = ensure_repo(UBOOT_REPO, CACHE_DIR / "u-boot", UBOOT_REF)
    checkout_ref(repo_path, UBOOT_REF)

    arm_makefile = repo_path / "arch" / "arm" / "Makefile"
    if arm_makefile.exists():
        makefile_text = arm_makefile.read_text()
        replacement = makefile_text.replace(
            "arch-$(CONFIG_CPU_ARM1136)\t=-march=armv5",
            "arch-$(CONFIG_CPU_ARM1136)\t=-march=armv5te",
        )
        if replacement == makefile_text:
            replacement = makefile_text.replace(
                "arch-$(CONFIG_CPU_ARM1136)      =-march=armv5",
                "arch-$(CONFIG_CPU_ARM1136)      =-march=armv5te",
            )
        if replacement == makefile_text:
            replacement = makefile_text.replace(
                "arch-$(CONFIG_CPU_ARM1136)   =-march=armv5",
                "arch-$(CONFIG_CPU_ARM1136)   =-march=armv5te",
            )
        if replacement != makefile_text:
            arm_makefile.write_text(replacement)
            LOG.info("Patched %s to use -march=armv5te", arm_makefile.relative_to(repo_path))
        else:
            LOG.debug("arm1136 march flag already modern or pattern missing")

    run_command(["make", "distclean"], cwd=repo_path, env=env)
    run_command(["make", UBOOT_CONFIG], cwd=repo_path, env=env)
    run_command(["make", f"-j{os.cpu_count() or 1}"], cwd=repo_path, env=env)

    artefact = repo_path / "u-boot.bin"
    if not artefact.exists():
        raise RuntimeError("U-Boot build did not produce u-boot.bin")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artefact, OUTPUT_DIR / "u-boot.bin")
    LOG.info("Copied %s", OUTPUT_DIR / "u-boot.bin")


def build_kernel(_: argparse.Namespace) -> None:
    env = configure_toolchain_env()
    env["KCFLAGS"] = "-march=armv6 -mtune=arm1136jf-s -mfloat-abi=softfp -mfpu=vfp"

    repo_path = ensure_repo(KERNEL_REPO, CACHE_DIR / "linux", KERNEL_REF)
    checkout_ref(repo_path, KERNEL_REF)

    run_command(["make", "mrproper"], cwd=repo_path, env=env)
    run_command(["make", KERNEL_DEFCONFIG], cwd=repo_path, env=env)
    run_command(["make", f"-j{os.cpu_count() or 1}", "zImage"], cwd=repo_path, env=env)

    image_path = repo_path / "arch" / "arm" / "boot" / "zImage"
    if not image_path.exists():
        raise RuntimeError("Kernel build did not produce zImage")

    shutil.copy2(image_path, OUTPUT_DIR / "zImage")
    LOG.info("Copied %s", OUTPUT_DIR / "zImage")


def build_dtb(_: argparse.Namespace) -> None:
    env = configure_toolchain_env()
    env["KCFLAGS"] = "-march=armv6 -mtune=arm1136jf-s -mfloat-abi=softfp -mfpu=vfp"

    repo_path = ensure_repo(KERNEL_REPO, CACHE_DIR / "linux", KERNEL_REF)
    checkout_ref(repo_path, KERNEL_REF)

    run_command(["make", KERNEL_DEFCONFIG], cwd=repo_path, env=env)
    run_command(["make", f"-j{os.cpu_count() or 1}", DTB_TARGET], cwd=repo_path, env=env)

    dtb_path = repo_path / DTB_TARGET
    if not dtb_path.exists():
        raise RuntimeError("Device tree build did not produce expected DTB")

    destination = OUTPUT_DIR / Path(DTB_TARGET).name
    shutil.copy2(dtb_path, destination)
    LOG.info("Copied %s", destination)


def ensure_mkimage() -> None:
    ensure_command_available("mkimage")


def build_boot(_: argparse.Namespace) -> None:
    if not BOOT_CMD.exists():
        raise RuntimeError(f"boot command file missing: {BOOT_CMD}")

    ensure_mkimage()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    LOG.info("Generated %s", BOOT_SCR)


def run_rootfs(_: argparse.Namespace) -> None:
    require_linux()
    require_root_privileges()

    ensure_command_available("debootstrap")

    rootfs_dir = OUTPUT_DIR / "rootfs"

    prepare_output_directory(rootfs_dir)

    # First stage bootstrap extracts the base system.
    bootstrap_cmd = [
        "debootstrap",
        "--arch",
        ROOTFS_ARCH,
        "--variant",
        "minbase",
        "--foreign",
        ROOTFS_SUITE,
        str(rootfs_dir),
        ROOTFS_MIRROR,
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
        LOG.info("Installed emulator at %s", qemu_target_path.relative_to(rootfs_dir))
    else:
        LOG.warning("qemu-arm-static not found; skipping emulator copy")

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

    LOG.info(
        "Root filesystem for Debian %s (%s) created at %s",
        ROOTFS_SUITE,
        ROOTFS_ARCH,
        rootfs_dir,
    )


@contextlib.contextmanager
def attached_loop_device(image: Path) -> "Generator[str, None, None]":
    result = run_command(
        ["losetup", "--find", "--show", "--partscan", str(image)],
        capture_output=True,
    )
    device = result.output.strip()
    if not device:
        raise RuntimeError("losetup did not return a loop device")
    LOG.info("Attached %s to %s", image, device)
    try:
        yield device
    finally:
        run_command(["losetup", "-d", device], check=False)
        LOG.info("Detached %s", device)


@contextlib.contextmanager
def mounted(device: str, mount_point: Path) -> "Generator[None, None, None]":
    run_command(["mount", device, str(mount_point)])
    try:
        yield
    finally:
        run_command(["umount", str(mount_point)], check=False)


def partition_image(image: Path) -> None:
    boot_start = 2048
    boot_size = BOOT_PARTITION_SIZE_MB * 1024 * 1024 // 512
    root_start = boot_start + boot_size

    sfdisk_script = dedent(
        f"""
        label: dos
        label-id: 0xfeedcafe
        unit: sectors

        {boot_start},{boot_size},c,*
        {root_start},,83
        """
    ).lstrip()

    run_command(["sfdisk", str(image)], capture_output=True, input_text=sfdisk_script)


def populate_boot_partition(mount_point: Path) -> None:
    required = {
        "u-boot.bin": OUTPUT_DIR / "u-boot.bin",
        "zImage": OUTPUT_DIR / "zImage",
        Path(DTB_TARGET).name: OUTPUT_DIR / Path(DTB_TARGET).name,
        "boot.scr": BOOT_SCR,
    }
    for label, source in required.items():
        if not source.exists():
            raise RuntimeError(f"Required artefact missing for boot partition: {source}")
        shutil.copy2(source, mount_point / label)
        LOG.info("Copied %s -> %s", source, mount_point / label)


def populate_root_partition(mount_point: Path) -> None:
    rootfs_dir = OUTPUT_DIR / "rootfs"
    if not rootfs_dir.exists():
        raise RuntimeError("Root filesystem not found. Run the rootfs step first.")

    for item in rootfs_dir.iterdir():
        destination = mount_point / item.name
        if item.is_dir():
            shutil.copytree(item, destination, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)
        LOG.info("Installed %s", destination)


def build_image(_: argparse.Namespace) -> None:
    require_linux()
    require_root_privileges()

    for command in ["losetup", "sfdisk", "mkfs.vfat", "mkfs.ext4", "truncate", "mount", "umount"]:
        ensure_command_available(command)

    image_path = OUTPUT_DIR / "ubiq480.img"
    if image_path.exists():
        LOG.info("Removing previous image: %s", image_path)
        image_path.unlink()

    run_command(["truncate", "--size", f"{IMAGE_SIZE_MB}M", str(image_path)])
    partition_image(image_path)

    with attached_loop_device(image_path) as loop:
        boot_dev = f"{loop}p1"
        root_dev = f"{loop}p2"

        run_command(["mkfs.vfat", "-F", "32", "-n", BOOT_LABEL, boot_dev])
        run_command(["mkfs.ext4", "-L", ROOT_LABEL, root_dev])

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            boot_mount = tmp_path / "boot"
            root_mount = tmp_path / "root"
            boot_mount.mkdir()
            root_mount.mkdir()

            with mounted(boot_dev, boot_mount):
                populate_boot_partition(boot_mount)

            with mounted(root_dev, root_mount):
                populate_root_partition(root_mount)

    LOG.info("Created bootable image at %s", image_path)


def check_dependencies(_: argparse.Namespace) -> None:
    missing = find_missing_commands(ALL_DEPENDENCIES)
    if missing:
        for command in missing:
            hint = DEPENDENCY_HINTS.get(command)
            if hint:
                LOG.error("Missing dependency '%s'. Install via: %s", command, hint)
            else:
                LOG.error("Missing dependency '%s'", command)
        raise RuntimeError(
            "One or more required tools are unavailable. Install the missing dependencies and retry."
        )
    LOG.info("All required build dependencies are available.")


STAGE_EXECUTORS: dict[str, Callable[[argparse.Namespace], None]] = {
    "deps": check_dependencies,
    "uboot": build_uboot,
    "kernel": build_kernel,
    "dtb": build_dtb,
    "boot": build_boot,
    "rootfs": run_rootfs,
    "image": build_image,
}


def run_all(args: argparse.Namespace) -> None:
    for stage in PIPELINE_ORDER:
        STAGE_EXECUTORS[stage](args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build utilities for the Ubiq480 project")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Automatically confirm the artefact summary prompts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    deps_parser = subparsers.add_parser("deps", help="Validate build-time dependencies")
    deps_parser.set_defaults(func=check_dependencies)

    uboot_parser = subparsers.add_parser("uboot", help="Build the U-Boot bootloader")
    uboot_parser.set_defaults(func=build_uboot)

    kernel_parser = subparsers.add_parser("kernel", help="Build the Linux kernel image")
    kernel_parser.set_defaults(func=build_kernel)

    dtb_parser = subparsers.add_parser("dtb", help="Compile the platform device tree")
    dtb_parser.set_defaults(func=build_dtb)

    boot_parser = subparsers.add_parser("boot", help="Generate the boot.scr script image")
    boot_parser.set_defaults(func=build_boot)

    rootfs_parser = subparsers.add_parser(
        "rootfs", help="Generate the Debian Bookworm armel root filesystem"
    )
    rootfs_parser.set_defaults(func=run_rootfs)

    image_parser = subparsers.add_parser("image", help="Assemble the complete microSD image")
    image_parser.set_defaults(func=build_image)

    all_parser = subparsers.add_parser("all", help="Execute the full build pipeline")
    all_parser.set_defaults(func=run_all)

    args = parser.parse_args(argv)
    setup_logging()
    if not confirm_execution(args.command, assume_yes=args.yes):
        return 1
    try:
        args.func(args)
    except RuntimeError as exc:
        LOG.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
