#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
WRAPPER="${REPO_ROOT}/generate_boot_assets.py"

usage() {
    cat <<USAGE
Usage: ${0##*/} boot

This helper is retained for backwards compatibility. It now defers to
\`${WRAPPER##*/}\`, which installs the mkimage dependency when required and
regenerates \`boot/boot.scr\` on demand.
USAGE
}

if [[ $# -ne 1 ]] || [[ $1 != "boot" ]]; then
    usage >&2
    exit 1
fi

if [[ ! -x "${WRAPPER}" ]]; then
    echo "error: ${WRAPPER} missing or not executable" >&2
    exit 2
fi

exec "${WRAPPER}" boot
