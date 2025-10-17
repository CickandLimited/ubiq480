"""Utilities for parsing and formatting command progress output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

__all__ = [
    "ProgressUpdate",
    "ProgressParser",
    "GitProgressParser",
    "DebootstrapProgressParser",
    "ArchiveProgressParser",
    "get_progress_parser",
    "format_progress_message",
]


@dataclass
class ProgressUpdate:
    """Structured representation of an incremental progress update."""

    label: str
    percent: float | None = None
    current: int | None = None
    total: int | None = None
    size_bytes: float | None = None
    total_size_bytes: float | None = None
    speed_bytes_per_sec: float | None = None


class ProgressParser:
    """Base class for command-specific progress parsers."""

    def prepare(self, command: list[str]) -> list[str]:
        """Return ``command`` potentially augmented for progress output."""

        return command

    def parse(self, text: str) -> list[ProgressUpdate]:
        """Return progress updates extracted from *text*."""

        raise NotImplementedError


class GitProgressParser(ProgressParser):
    """Parse progress lines emitted by ``git`` commands."""

    _PROGRESS_RE = re.compile(
        r"^(?:remote:\s+)?(?P<label>[A-Za-z ]+):\s+"
        r"(?P<percent>\d+)%\s+\((?P<current>[\d,]+)/(?P<total>[\d,]+)\)"
        r"(?:,\s*(?P<size>[^|,]+))?"
        r"(?:\s+\|\s+(?P<speed>[^,]+))?"
        r"(?:,\s*done\.)?$"
    )

    def prepare(self, command: list[str]) -> list[str]:
        if "--progress" in command:
            return command
        prepared = command[:]
        insertion_point = 2 if len(prepared) >= 2 else len(prepared)
        prepared.insert(insertion_point, "--progress")
        return prepared

    def parse(self, text: str) -> list[ProgressUpdate]:
        match = self._PROGRESS_RE.match(text.strip())
        if not match:
            return []
        label = match.group("label").strip()
        percent = float(match.group("percent"))
        current = _parse_int(match.group("current"))
        total = _parse_int(match.group("total"))
        size = _parse_size(match.group("size")) if match.group("size") else None
        speed = _parse_rate(match.group("speed")) if match.group("speed") else None
        return [
            ProgressUpdate(
                label=label,
                percent=percent,
                current=current,
                total=total,
                size_bytes=size,
                speed_bytes_per_sec=speed,
            )
        ]


class DebootstrapProgressParser(ProgressParser):
    """Parse progress lines emitted by ``debootstrap``."""

    _PROGRESS_RE = re.compile(
        r"^Progress:\s*(?P<percent>\d+)%" r"(?:\s*\((?P<label>[^)]+)\))?"
    )

    def parse(self, text: str) -> list[ProgressUpdate]:
        match = self._PROGRESS_RE.match(text.strip())
        if not match:
            return []
        label = match.group("label") or "debootstrap"
        percent = float(match.group("percent"))
        return [ProgressUpdate(label=label.strip(), percent=percent)]


class ArchiveProgressParser(ProgressParser):
    """Parse generic archive extraction progress lines."""

    _PROGRESS_RE = re.compile(
        r"^(?P<label>[A-Za-z ]+):?\s+"
        r"(?P<percent>\d+)%"
        r"(?:\s*\((?P<current>[\d,]+)/(?P<total>[\d,]+)\))?"
        r"(?:,\s*(?P<size>[^@]+?))?"
        r"(?:\s*@\s*(?P<speed>.+))?"
        r"$"
    )

    def parse(self, text: str) -> list[ProgressUpdate]:
        match = self._PROGRESS_RE.match(text.strip())
        if not match:
            return []
        label = match.group("label").strip()
        percent = float(match.group("percent"))
        current = _parse_optional_int(match.group("current"))
        total = _parse_optional_int(match.group("total"))
        size = _parse_size(match.group("size")) if match.group("size") else None
        speed = _parse_rate(match.group("speed")) if match.group("speed") else None
        return [
            ProgressUpdate(
                label=label,
                percent=percent,
                current=current,
                total=total,
                size_bytes=size,
                speed_bytes_per_sec=speed,
            )
        ]


def get_progress_parser(command: Sequence[str]) -> tuple[ProgressParser | None, list[str]]:
    """Return a parser suitable for *command* alongside the prepared command."""

    if not command:
        return None, list(command)

    program = Path(command[0]).name
    if program == "git" and len(command) >= 2 and command[1] in {"clone", "fetch"}:
        parser = GitProgressParser()
        prepared = parser.prepare(list(command))
        return parser, prepared
    if program == "debootstrap":
        return DebootstrapProgressParser(), list(command)
    if program in {"tar", "bsdtar"} and _looks_like_extraction(command[1:]):
        return ArchiveProgressParser(), list(command)
    return None, list(command)


def format_progress_message(update: ProgressUpdate) -> str:
    """Return a human-readable string representing *update*."""

    parts: list[str] = [update.label]
    if update.percent is not None:
        parts.append(f"{update.percent:.0f}%")
    if update.current is not None:
        if update.total is not None:
            parts.append(f"({update.current}/{update.total})")
        else:
            parts.append(f"({update.current})")
    if update.size_bytes is not None:
        size_text = _format_bytes(update.size_bytes)
        if update.total_size_bytes is not None:
            total_text = _format_bytes(update.total_size_bytes)
            parts.append(f"{size_text} / {total_text}")
        else:
            parts.append(size_text)
    if update.speed_bytes_per_sec is not None:
        parts.append(f"@ {_format_bytes(update.speed_bytes_per_sec)}/s")
    return " ".join(part for part in parts if part)


def _looks_like_extraction(arguments: Sequence[str]) -> bool:
    for arg in arguments:
        if arg.startswith("-x") or arg in {"--extract", "--get", "x", "xf"}:
            return True
    return False


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    return _parse_int(value)


def _parse_int(value: str) -> int:
    return int(value.replace(",", ""))


_SIZE_RE = re.compile(r"^(?P<number>[\d.,]+)\s*(?P<unit>[A-Za-z/]+)$")


def _parse_size(value: str) -> float | None:
    match = _SIZE_RE.match(value.strip())
    if not match:
        return None
    number_text = match.group("number").replace(",", "")
    try:
        number = float(number_text)
    except ValueError:
        return None
    unit = match.group("unit")
    if unit.endswith("/s"):
        unit = unit[:-2]
    unit_multipliers = {
        "B": 1,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "PB": 1000**5,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "TiB": 1024**4,
        "PiB": 1024**5,
    }
    multiplier = unit_multipliers.get(unit)
    if multiplier is None:
        return None
    return number * multiplier


def _parse_rate(value: str) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.endswith("/s"):
        cleaned = cleaned[:-2].strip()
    return _parse_size(cleaned)


def _format_bytes(value: float) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    abs_value = abs(value)
    unit_index = 0
    while abs_value >= 1024 and unit_index < len(units) - 1:
        abs_value /= 1024
        value /= 1024
        unit_index += 1
    if abs_value >= 10 or unit_index == 0:
        formatted = f"{value:.0f}"
    else:
        formatted = f"{value:.1f}"
    return f"{formatted} {units[unit_index]}"
