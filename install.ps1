$ErrorActionPreference = "Stop"
$Repository = "https://github.com/Prithibi17/anme-cli.git"
$Checkout = Join-Path ([System.IO.Path]::GetTempPath()) ("anme-cli-" + [guid]::NewGuid())

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git for Windows is required. Install it from https://git-scm.com/download/win"
    }
    git clone --depth 1 $Repository $Checkout
    if ($LASTEXITCODE -ne 0) { throw "Could not download anme-cli." }
    & (Join-Path $Checkout "tui/install.ps1")
} finally {
    Remove-Item -LiteralPath $Checkout -Recurse -Force -ErrorAction SilentlyContinue
}
