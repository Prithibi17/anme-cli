#!/bin/sh
set -eu

install_root="${XDG_DATA_HOME:-$HOME/.local/share}/anme-cli"
bin_dir="${HOME}/.local/bin"

python3 -m venv "$install_root"
"$install_root/bin/python" -m pip install --upgrade pip
"$install_root/bin/pip" install --upgrade "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cp "$script_dir/../anme-cli" "$install_root/bin/anme-cli-backend"
chmod +x "$install_root/bin/anme-cli-backend"
mkdir -p "$bin_dir"
ln -sf "$install_root/bin/anme-cli" "$bin_dir/anme-cli"

printf 'Installed anme-cli at %s\n' "$bin_dir/anme-cli"
printf 'Ensure %s is in PATH, then run: anme-cli\n' "$bin_dir"
