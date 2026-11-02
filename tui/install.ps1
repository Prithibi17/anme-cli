$ErrorActionPreference = "Stop"

$InstallRoot = Join-Path $env:LOCALAPPDATA "anme-cli"
$UserBin = Join-Path $HOME "bin"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundledMpvDir = Join-Path $InstallRoot "mpv"

$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Python) { throw "Python 3.10 or newer is required." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git for Windows is required." }

# Install a self-contained MPV build when Windows does not already provide one.
# Keeping it below InstallRoot also makes uninstall remove it cleanly.
if (-not (Get-Command mpv.exe -ErrorAction SilentlyContinue) -and
    -not (Test-Path -LiteralPath (Join-Path $BundledMpvDir "mpv.exe"))) {
    Write-Host "MPV was not found; installing the latest stable Windows build..."
    $Release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/mpv-distributions/mpv-windows-setup/releases/latest" `
        -Headers @{ "User-Agent" = "anme-cli-installer" }
    $Architecture = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "aarch64" } else { "x86_64" }
    $Asset = $Release.assets | Where-Object {
        $_.name -match "^mpv-setup-$Architecture-[0-9].*\.exe$"
    } | Select-Object -First 1
    if (-not $Asset) { throw "Could not find a compatible MPV installer for $Architecture." }

    $MpvInstaller = Join-Path ([System.IO.Path]::GetTempPath()) $Asset.name
    try {
        Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $MpvInstaller
        $MpvInstallProcess = Start-Process `
            -FilePath $MpvInstaller `
            -ArgumentList @(
                "/CURRENTUSER",
                "/SP-",
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/DIR=`"$BundledMpvDir`""
            ) `
            -Wait `
            -PassThru
        if ($MpvInstallProcess.ExitCode -ne 0) {
            throw "MPV installer exited with code $($MpvInstallProcess.ExitCode)."
        }
    } finally {
        Remove-Item -LiteralPath $MpvInstaller -Force -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path -LiteralPath (Join-Path $BundledMpvDir "mpv.exe"))) {
        throw "MPV installation completed, but mpv.exe was not found in $BundledMpvDir."
    }
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
"@echo off`r`nset `"PATH=$BundledMpvDir;%PATH%`"`r`n`"$InstallRoot\Scripts\anme-cli.exe`" %*`r`n" | Set-Content -Path $Launcher -Encoding ASCII

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
if (($env:Path -split ";") -notcontains $BundledMpvDir) {
    $env:Path = "$BundledMpvDir;$env:Path"
}

if (-not (Test-Path -LiteralPath $Launcher)) {
    throw "Installation finished, but the anme-cli launcher was not created at $Launcher"
}

Write-Host "Installed anme-cli successfully."
Write-Host "Run now: anme-cli"
Write-Host "Launcher: $Launcher"
Write-Host "Player: $((Get-Command mpv.exe -ErrorAction SilentlyContinue).Source)"
