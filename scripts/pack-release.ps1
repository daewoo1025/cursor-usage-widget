param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$DistApp = Join-Path $Root "dist\CursorWidget"
$ReleaseDir = Join-Path $Root "release"
$ZipName = "CursorWidget-Windows-v$Version.zip"
$ZipPath = Join-Path $ReleaseDir $ZipName
$exePath = Join-Path $DistApp "CursorWidget.exe"

if (-not (Test-Path $exePath)) {
    throw "Missing dist\CursorWidget\CursorWidget.exe. Run scripts\build.bat first."
}

Write-Host "Packaging release v$Version ..."

# Stop common lockers
Get-Process -Name "CursorWidget" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

# Drop helper files into the app folder for the zip, then remove after
$startBat = Join-Path $DistApp "Start Cursor Widget.bat"
$readme = Join-Path $DistApp "README.txt"

@"
@echo off
cd /d "%~dp0"
start "" "%~dp0CursorWidget.exe"
"@ | Set-Content -Path $startBat -Encoding ASCII

@"
Cursor Pro+ Glass Desktop Widget
================================

QUICK START
1. Keep this whole folder together (do not move only the .exe).
2. Double-click "Start Cursor Widget.bat" or CursorWidget.exe.
3. Sign in to Cursor IDE on this PC at least once (the widget reads local auth).
4. You should see Live Sync. If not, open Settings (gear) and paste
   WorkosCursorSessionToken from https://cursor.com cookies.

REQUIREMENTS
- Windows 10/11 (64-bit)
- Cursor IDE installed and logged in (recommended)
- Internet access to cursor.com

NOTES
- First launch may show a Windows SmartScreen warning because the app is unsigned.
  Click More info -> Run anyway if you trust the release.
- Optional saved token lives only on your PC:
  %USERPROFILE%\.cursor_widget_config.json
- Unofficial project — not affiliated with Cursor / Anysphere.
"@ | Set-Content -Path $readme -Encoding UTF8

try {
    # tar.exe is more reliable than Compress-Archive on large Qt trees
    # Creates a zip whose root folder is CursorWidget-Windows
    $stageName = "CursorWidget-Windows"
    $stage = Join-Path $ReleaseDir $stageName
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    New-Item -ItemType Directory -Path $stage | Out-Null

    # Hardlink/junction is fragile on Windows; use robocopy then tar
    & robocopy $DistApp $stage /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    # robocopy exit codes 0-7 are success
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }

    Push-Location $ReleaseDir
    try {
        & tar.exe -a -cf $ZipName $stageName
        if ($LASTEXITCODE -ne 0) { throw "tar failed with code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }

    Remove-Item -Recurse -Force $stage
} finally {
    Remove-Item -Force $startBat -ErrorAction SilentlyContinue
    Remove-Item -Force $readme -ErrorAction SilentlyContinue
}

$sizeMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Created: $ZipPath ($sizeMb MB)"
Write-Host "Upload this zip as a GitHub Release asset."
