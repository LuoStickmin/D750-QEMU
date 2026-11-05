<#
.SYNOPSIS
    Run the D750 validation prototype and keep the evidence.

.EXAMPLE
    .\Run-D750.ps1 -Payload C:\fw\b1010_115a.bin -Flash C:\fw\a1010_011100.bin
    .\Run-D750.ps1 -Payload ... -Flash ... -Gdb -RunSeconds 3 -Checkpoint 0x9025D720
    .\Run-D750.ps1 -Payload ... -Strict -Timeout 5
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Payload,
    [string]$Flash = "",
    [double]$Timeout = 10,
    [switch]$Strict,
    [switch]$Gdb,
    [double]$RunSeconds = 3,
    [string]$Checkpoint = "",
    [string]$Entry = "",
    [string]$Qemu = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "python not found on PATH" }
if (-not (Test-Path $Payload)) { throw "payload not found: $Payload" }
if ($Flash -and -not (Test-Path $Flash)) { throw "flash image not found: $Flash" }

$runArgs = @("tools/run.py", "--payload", $Payload, "--timeout", $Timeout)
if ($Flash) { $runArgs += @("--flash", $Flash) }
if ($Strict) { $runArgs += "--strict" }
if ($Qemu) { $runArgs += @("--qemu", $Qemu) }
if ($Entry) { $runArgs += @("--entry", $Entry) }
if ($Gdb) {
    $runArgs += @("--gdb", "--run-seconds", $RunSeconds)
    if ($Checkpoint) { $runArgs += @("--checkpoint", $Checkpoint) }
}

& $python.Source @runArgs
exit $LASTEXITCODE
