# CLM-1 per-user installer for Windows 10/11.
$ErrorActionPreference = "Stop"
$SourceDir = $PSScriptRoot
$AppDir = Join-Path $env:LOCALAPPDATA "CLM-1"
$Version = "1.8.0"
$Required = @("clm", "clm_ai.py", "clm_flash.py", "clm_paths.py", "clm_doctor.py", "clm_update.py", "clm_firmware.ino", "TERMS_OF_USE.md", "requirements.txt")
foreach ($File in $Required) {
    if (-not (Test-Path (Join-Path $SourceDir $File) -PathType Leaf)) { throw "Required project file is missing: $File" }
}
$PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
$VenvPython = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    if ($PythonLauncher) {
        & py -3 -m venv (Join-Path $AppDir ".venv")
    } elseif ($PythonCommand) {
        & python -m venv (Join-Path $AppDir ".venv")
    } else {
        throw "Python 3.10 or newer is required. Install it from https://www.python.org/downloads/windows/."
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not create the CLM-1 Python environment." }
}
foreach ($File in $Required) { Copy-Item -Force (Join-Path $SourceDir $File) (Join-Path $AppDir $File) }
foreach ($File in @("README.md", "COMMANDS.txt", "CHANGELOG.md", "LICENSE")) {
    $Path = Join-Path $SourceDir $File
    if (Test-Path $Path -PathType Leaf) { Copy-Item -Force $Path (Join-Path $AppDir $File) }
}
& $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "CLM-1 requires Python 3.10 or newer. Install a newer Python and rerun this installer." }
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not update pip in the CLM-1 environment." }
& $VenvPython -m pip install -r (Join-Path $AppDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install CLM-1 dependencies." }
$CrLf = [char]13 + [char]10
$ClmShim = '@echo off' + $CrLf + '"%~dp0.venv\Scripts\python.exe" "%~dp0clm" %*' + $CrLf
$FlashShim = '@echo off' + $CrLf + '"%~dp0.venv\Scripts\python.exe" "%~dp0clm" clm_h@cker_init %*' + $CrLf
Set-Content -Encoding ASCII -Path (Join-Path $AppDir "clm.cmd") -Value $ClmShim
Set-Content -Encoding ASCII -Path (Join-Path $AppDir "clm_h@cker_init.cmd") -Value $FlashShim
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathEntries = @()
if ($UserPath) { $PathEntries = $UserPath -split ";" | Where-Object { $_ } }
if ($PathEntries -notcontains $AppDir) {
    [Environment]::SetEnvironmentVariable("Path", ((@($PathEntries) + @($AppDir)) -join ";"), "User")
}
if (($env:Path -split ";") -notcontains $AppDir) { $env:Path = "$env:Path;$AppDir" }
Write-Host ""
Write-Host "CLM-1 v$Version installed for Windows."
Write-Host "Open a new PowerShell/Terminal window, then run: clm"
Write-Host "Direct firmware flasher: clm_h@cker_init"
Write-Host "Firmware and terms: $AppDir"
