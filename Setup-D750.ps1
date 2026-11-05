<#
.SYNOPSIS
    Build the nikon-d750 QEMU overlay.

.DESCRIPTION
    Thin wrapper around tools/build.py.  It does not download or embed any
    Nikon firmware.  Run it from the repository root after installing the
    MSYS2 UCRT64 dependencies listed in docs/build.md.

.EXAMPLE
    .\Setup-D750.ps1
    .\Setup-D750.ps1 -MsysRoot D:\msys64 -Jobs 8
    .\Setup-D750.ps1 -Archive D:\downloads\qemu-11.1.0.tar.xz
#>
[CmdletBinding()]
param(
    [string]$MsysRoot = "C:\msys64",
    [int]$Jobs = 4,
    [string]$Archive = "",
    [string]$Main = "",
    [string]$Flash = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "python not found on PATH; install Python 3.12+ first"
}

$buildArgs = @("tools/build.py", "--msys-root", $MsysRoot, "--jobs", $Jobs)
if ($Archive) {
    $buildArgs += @("--archive", $Archive)
}

Write-Host "== building qemu-system-arm with the nikon-d750 overlay =="
& $python.Source @buildArgs
if ($LASTEXITCODE -ne 0) {
    throw "build failed (exit $LASTEXITCODE); see docs/build.md"
}

$qemu = Join-Path $root ".build\build\qemu-system-arm.exe"
if (-not (Test-Path $qemu)) {
    throw "build reported success but $qemu is missing"
}
Write-Host "== machine check =="
& $qemu -M help | Select-String "nikon-d750"

if ($Main) {
    Write-Host "== static profile scan =="
    $scanArgs = @("tools/fwscan.py", "--main", $Main,
                  "--out", "analysis\d750-0115.json")
    if ($Flash) { $scanArgs += @("--flash", $Flash) }
    & $python.Source @scanArgs
}
Write-Host "done. next: .\Run-D750.ps1 -Payload <b1010> -Flash <a1010>"
