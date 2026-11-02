$ErrorActionPreference = "Stop"

$InstallRoot = Join-Path $env:LOCALAPPDATA "anme-cli"
$UserBin = Join-Path $HOME "bin"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Python) { throw "Python 3.10 or newer is required." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git for Windows is required." }
if (-not (Get-Command mpv -ErrorAction SilentlyContinue)) {
    Write-Warning "MPV was not found in PATH. Install MPV before playing video."
}

if ($Python.Name -eq "py.exe" -or $Python.Name -eq "py") {
    & $Python.Source -3 -m venv $InstallRoot
} else {
    & $Python.Source -m venv $InstallRoot
}

$VenvPython = Join-Path $InstallRoot "Scripts/python.exe"
$VenvPip = Join-Path $InstallRoot "Scripts/pip.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPip install --upgrade $ScriptDir
Copy-Item (Join-Path $ScriptDir "../anme-cli") (Join-Path $InstallRoot "Scripts/anme-cli-backend") -Force

New-Item -ItemType Directory -Path $UserBin -Force | Out-Null
$Launcher = Join-Path $UserBin "anme-cli.cmd"
"@echo off`r`n`"$InstallRoot\Scripts\anme-cli.exe`" %*`r`n" | Set-Content -Path $Launcher -Encoding ASCII

$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($CurrentPath -split ";") -notcontains $UserBin) {
    $NewPath = if ($CurrentPath) { "$CurrentPath;$UserBin" } else { $UserBin }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
}

# Updating the persistent user PATH does not update the PowerShell process that
# is currently running. Add the launcher directory to this process as well so
# the command works immediately after `irm ... | iex` finishes.
if (($env:Path -split ";") -notcontains $UserBin) {
    $env:Path = "$UserBin;$env:Path"
}

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "Installation finished, but the anme-cli launcher was not created at $Launcher"
}

Write-Host "Installed anme-cli successfully."
Write-Host "Run now: anme-cli"
Write-Host "Launcher: $Launcher"
