#!/bin/sh
set -eu

repository="https://github.com/Prithibi17/anme-cli.git"
checkout="$(mktemp -d "${TMPDIR:-/tmp}/anme-cli.XXXXXX")"

cleanup() {
    find "$checkout" -depth -type f -delete 2>/dev/null || true
    find "$checkout" -depth -type d -empty -delete 2>/dev/null || true
}
trap cleanup EXIT INT HUP TERM

command -v git >/dev/null 2>&1 || {
    printf 'Error: git is required.\n' >&2
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    printf 'Error: Python 3.10 or newer is required.\n' >&2
    exit 1
}

git clone --depth 1 "$repository" "$checkout/repository"
"$checkout/repository/tui/install.sh"
