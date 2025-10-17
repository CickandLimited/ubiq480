"""Shared helpers for ensuring host tooling is available.

The Ubiq480 build utilities can bootstrap a development environment by
attempting to install missing commands via the system package manager and by
provisioning a Python virtual environment for any runtime dependencies listed in
``requirements.txt``.  These helpers centralise the logic so both ``build.py``
and ``generate_boot_assets.py`` can reuse the same behaviour.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence

LOG = logging.getLogger("ubiq480.bootstrap")

_bootstrap_enabled = True
_apt_updated = False

APT_PACKAGE_MAP: dict[str, Sequence[str]] = {
    "git": ["git"],
    "make": ["make"],
    "arm-linux-gnueabi-gcc": ["gcc-arm-linux-gnueabi"],
    "arm-linux-gnueabi-ld": ["binutils-arm-linux-gnueabi"],
    "debootstrap": ["debootstrap"],
    "flex": ["flex"],
    "mkimage": ["u-boot-tools"],
    "losetup": ["util-linux"],
    "sfdisk": ["fdisk"],
    "mkfs.vfat": ["dosfstools"],
    "mkfs.ext4": ["e2fsprogs"],
    "truncate": ["coreutils"],
    "mount": ["util-linux"],
    "umount": ["util-linux"],
}

DNF_PACKAGE_MAP: dict[str, Sequence[str]] = {
    "git": ["git"],
    "make": ["make"],
    "arm-linux-gnueabi-gcc": ["gcc-arm-linux-gnu"],
    "arm-linux-gnueabi-ld": ["binutils-arm-linux-gnu"],
    "debootstrap": ["debootstrap"],
    "flex": ["flex"],
    "mkimage": ["uboot-tools"],
    "losetup": ["util-linux"],
    "sfdisk": ["util-linux"],
    "mkfs.vfat": ["dosfstools"],
    "mkfs.ext4": ["e2fsprogs"],
    "truncate": ["coreutils"],
    "mount": ["util-linux"],
    "umount": ["util-linux"],
}

PACKAGE_MAP: dict[str, Mapping[str, Sequence[str]]] = {
    "apt-get": APT_PACKAGE_MAP,
    "dnf": DNF_PACKAGE_MAP,
}

PYTHON_VENV_PACKAGES: dict[str, Sequence[str]] = {
    "apt-get": ["python3-venv"],
    "dnf": ["python3-venv"],
}


def set_bootstrap_enabled(enabled: bool) -> None:
    """Globally enable or disable automatic dependency installation."""

    global _bootstrap_enabled
    _bootstrap_enabled = enabled


def ensure_commands(
    commands: Iterable[str],
    *,
    hints: Mapping[str, str] | None = None,
    logger: logging.Logger | None = None,
) -> list[str]:
    """Ensure all *commands* are available, attempting installation if allowed.

    Returns a list of commands that remain missing after any attempted
    bootstrapping efforts.
    """

    logger = logger or LOG
    commands = list(dict.fromkeys(commands))
    missing = [cmd for cmd in commands if shutil.which(cmd) is None]
    if not missing:
        return []

    if not _bootstrap_enabled:
        return missing

    manager = _detect_package_manager()
    if not manager:
        logger.debug("No supported package manager found for automatic installation.")
        return missing

    packages = _collect_packages(manager, missing)
    if not packages:
        logger.debug("No package mapping available for missing commands: %s", ", ".join(missing))
        return missing

    try:
        _install_packages(manager, packages, logger)
    except PermissionError:
        logger.warning(
            "Automatic installation skipped because elevated privileges are required and sudo is unavailable."
        )
        return missing
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Automatic installation via %s failed with exit code %s.", manager, exc.returncode
        )
        return [cmd for cmd in commands if shutil.which(cmd) is None]

    return [cmd for cmd in commands if shutil.which(cmd) is None]


def ensure_tool(
    command: str,
    *,
    hints: Mapping[str, str] | None = None,
    logger: logging.Logger | None = None,
) -> None:
    """Ensure a single *command* exists or raise :class:`RuntimeError`."""

    remaining = ensure_commands([command], hints=hints, logger=logger)
    if remaining:
        hint = hints.get(command) if hints else None
        message = f"Required command '{command}' is not available."
        if hint:
            message = f"{message} Install it manually, for example: {hint}"
        raise RuntimeError(message)


def ensure_python_requirements(
    requirements: Path,
    venv_dir: Path,
    *,
    logger: logging.Logger | None = None,
) -> None:
    """Ensure Python dependencies declared in *requirements* are installed."""

    logger = logger or LOG
    if not requirements.exists():
        return

    meaningful = [
        line
        for line in (line.strip() for line in requirements.read_text().splitlines())
        if line and not line.startswith("#")
    ]

    if not _bootstrap_enabled:
        if venv_dir.exists():
            return
        manual = (
            f"Python requirements need to be installed manually. Create a virtual environment "
            f"at {venv_dir} and install {requirements.name}:\n"
            f"  python3 -m venv {venv_dir}\n  {venv_dir / 'bin' / 'pip'} install -r {requirements}"
        )
        raise RuntimeError(manual)

    python_executable = sys.executable
    logger.info("Ensuring Python virtual environment at %s", venv_dir)
    if not venv_dir.exists():
        _create_virtualenv(python_executable, venv_dir, logger)

    pip_dir = "Scripts" if os.name == "nt" else "bin"
    pip_path = venv_dir / pip_dir / "pip"
    if not pip_path.exists():  # pragma: no cover - unexpected venv layout
        _ensure_pip_available(python_executable, venv_dir, logger)
        if not pip_path.exists():
            raise RuntimeError(f"Virtual environment at {venv_dir} is missing pip")

    if meaningful:
        logger.info("Installing Python requirements from %s", requirements)
        _run([str(pip_path), "install", "-r", str(requirements)], logger)


def _create_virtualenv(python_executable: str, venv_dir: Path, logger: logging.Logger) -> None:
    try:
        _run([python_executable, "-m", "venv", str(venv_dir)], logger)
        return
    except subprocess.CalledProcessError as exc:
        logger.debug("python -m venv failed with exit code %s", exc.returncode)

    if not _bootstrap_enabled:
        raise

    if _ensure_python_venv_support(logger):
        if venv_dir.exists():
            shutil.rmtree(venv_dir, ignore_errors=True)
        _run([python_executable, "-m", "venv", str(venv_dir)], logger)
        return

    raise


def _ensure_pip_available(python_executable: str, venv_dir: Path, logger: logging.Logger) -> None:
    pip_dir = "Scripts" if os.name == "nt" else "bin"
    venv_python = venv_dir / pip_dir / ("python.exe" if os.name == "nt" else "python")

    if venv_python.exists():
        try:
            _run([str(venv_python), "-m", "ensurepip", "--upgrade"], logger)
        except subprocess.CalledProcessError as exc:
            logger.debug("ensurepip failed with exit code %s", exc.returncode)
        else:
            return

    if not _bootstrap_enabled:
        return

    if _ensure_python_venv_support(logger):
        _run([python_executable, "-m", "venv", "--clear", str(venv_dir)], logger)
        if venv_python.exists():
            _run([str(venv_python), "-m", "ensurepip", "--upgrade"], logger)


def _ensure_python_venv_support(logger: logging.Logger) -> bool:
    manager = _detect_package_manager()
    if not manager:
        logger.debug("No supported package manager available to install python venv support.")
        return False

    packages = PYTHON_VENV_PACKAGES.get(manager)
    if not packages:
        logger.debug("No python venv package mapping available for manager %s", manager)
        return False

    try:
        _install_packages(manager, packages, logger)
    except PermissionError:
        logger.warning(
            "Automatic installation of python virtual environment support requires elevated privileges."
        )
        return False
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Automatic installation of %s via %s failed with exit code %s.",
            ", ".join(packages),
            manager,
            exc.returncode,
        )
        return False

    return True


def _detect_package_manager() -> str | None:
    if shutil.which("apt-get"):
        return "apt-get"
    if shutil.which("dnf"):
        return "dnf"
    return None


def _collect_packages(manager: str, commands: Sequence[str]) -> list[str]:
    mapping = PACKAGE_MAP.get(manager, {})
    packages: set[str] = set()
    for command in commands:
        for package in mapping.get(command, []):
            packages.add(package)
    return sorted(packages)


def _install_packages(manager: str, packages: Sequence[str], logger: logging.Logger) -> None:
    prefix: list[str] = []
    if os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if not sudo:
            raise PermissionError
        prefix = [sudo]

    logger.info("Installing missing packages via %s: %s", manager, ", ".join(packages))

    command_prefix = prefix + [manager]
    if manager == "apt-get":
        _maybe_run_apt_update(command_prefix, logger)
        _run(command_prefix + ["install", "-y", *packages], logger)
    elif manager == "dnf":
        _run(command_prefix + ["install", "-y", *packages], logger)
    else:  # pragma: no cover - guard for future extensions
        raise RuntimeError(f"Unsupported package manager: {manager}")


def _maybe_run_apt_update(command_prefix: Sequence[str], logger: logging.Logger) -> None:
    global _apt_updated
    if _apt_updated:
        return
    _run(list(command_prefix) + ["update"], logger)
    _apt_updated = True


def _run(command: Sequence[str], logger: logging.Logger) -> None:
    logger.info("$ %s", " ".join(str(part) for part in command))
    subprocess.run(command, check=True)
