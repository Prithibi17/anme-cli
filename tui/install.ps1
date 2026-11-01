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

Write-Host "Installed anme-cli. Open a new terminal and run: anme-cli"
