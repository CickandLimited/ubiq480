"""Repository freshness verification for the Ubiq480 toolkit."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from textwrap import dedent

CANONICAL_REPOSITORY = "https://github.com/CickandLimited/ubiq480.git"
SKIP_ENVIRONMENT_FLAG = "UBIQ480_SKIP_SELF_CHECK"


def _run_git_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Execute a git command returning the completed process."""

    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _resolve_local_head(repo_root: Path) -> str:
    """Return the commit hash of the local checkout's HEAD."""

    result = _run_git_command(["rev-parse", "HEAD"], cwd=repo_root)
    return result.stdout.strip()


def _resolve_remote_head() -> str:
    """Return the commit hash referenced by the canonical repository HEAD."""

    result = _run_git_command(["ls-remote", CANONICAL_REPOSITORY, "HEAD"])
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.split()[0]
    raise RuntimeError("Canonical repository did not report a HEAD commit.")


def ensure_latest_checkout(repo_root: Path | None = None, *, logger: logging.Logger | None = None) -> None:
    """Abort execution when the checkout is out-of-date with the canonical repo."""

    if os.environ.get(SKIP_ENVIRONMENT_FLAG):
        if logger:
            logger.info("Skipping repository freshness check due to %s", SKIP_ENVIRONMENT_FLAG)
        return

    if repo_root is None:
        repo_root = Path(__file__).resolve().parent

    git_dir = repo_root / ".git"
    if not git_dir.exists():
        message = dedent(
            f"""
            Unable to verify the repository version because the checkout located at
            {repo_root} is missing its .git metadata. Clone the project directly from
            {CANONICAL_REPOSITORY} so the integrity check can run.
            """
        ).strip()
        if logger:
            logger.error(message)
        raise SystemExit(message)

    try:
        local_head = _resolve_local_head(repo_root)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive guard
        message = dedent(
            f"""
            Failed to determine the local repository state: {exc}. Please ensure git is
            available and the checkout is not corrupted.
            """
        ).strip()
        if logger:
            logger.error(message)
        raise SystemExit(message) from exc

    try:
        remote_head = _resolve_remote_head()
    except subprocess.CalledProcessError as exc:
        message = dedent(
            f"""
            Unable to contact the canonical repository at {CANONICAL_REPOSITORY} to
            confirm the latest version. Verify network connectivity or set
            {SKIP_ENVIRONMENT_FLAG}=1 to bypass the check temporarily.
            """
        ).strip()
        if logger:
            logger.error(message)
        raise SystemExit(message) from exc
    except RuntimeError as exc:
        message = str(exc)
        if logger:
            logger.error(message)
        raise SystemExit(message) from exc

    if local_head != remote_head:
        message = dedent(
            f"""
            This checkout (commit {local_head}) is out-of-date with the canonical
            repository HEAD ({remote_head}). Update the local copy by running:

                git fetch {CANONICAL_REPOSITORY}
                git reset --hard FETCH_HEAD

            Alternatively, clone a fresh copy directly from
            {CANONICAL_REPOSITORY}.
            """
        ).strip()
        if logger:
            logger.error(message)
        raise SystemExit(message)

    if logger:
        logger.info("Repository matches canonical HEAD %s", remote_head)

