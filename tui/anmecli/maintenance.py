from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPOSITORY = "https://github.com/Prithibi17/anme-cli.git"


def install_root() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "anme-cli"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "anme-cli"


def update() -> int:
    git = shutil.which("git")
    if not git:
        print("Error: Git is required to update anme-cli.", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="anme-cli-update-") as directory:
        checkout = Path(directory) / "repository"
        result = subprocess.run([git, "clone", "--depth", "1", REPOSITORY, str(checkout)])
        if result.returncode:
            return result.returncode
        if os.name == "nt":
            powershell = shutil.which("pwsh") or shutil.which("powershell")
            if not powershell:
                print("Error: PowerShell is required to update anme-cli.", file=sys.stderr)
                return 1
            command = [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(checkout / "tui/install.ps1"),
            ]
        else:
            command = ["sh", str(checkout / "tui/install.sh")]
        return subprocess.run(command).returncode


def uninstall() -> int:
    root = install_root()
    if os.name == "nt":
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            print("Error: PowerShell is required to uninstall anme-cli.", file=sys.stderr)
            return 1
        user_bin = Path.home() / "bin"
        cleanup = (
            "Start-Sleep -Seconds 1; "
            f"Remove-Item -LiteralPath '{root}' -Recurse -Force -ErrorAction SilentlyContinue; "
            f"Remove-Item -LiteralPath '{user_bin / 'anme-cli.cmd'}' -Force -ErrorAction SilentlyContinue"
        )
        subprocess.Popen(
            [powershell, "-NoProfile", "-WindowStyle", "Hidden", "-Command", cleanup],
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    else:
        link = Path.home() / ".local/bin/anme-cli"
        try:
            link.unlink(missing_ok=True)
        except OSError as error:
            print(f"Warning: could not remove {link}: {error}", file=sys.stderr)
        shutil.rmtree(root, ignore_errors=True)
    print("anme-cli has been uninstalled.")
    return 0
