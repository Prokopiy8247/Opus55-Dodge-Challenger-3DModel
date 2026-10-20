# Runs the Unity 6000.6.0f1 editor in batch mode with the Package Manager cache and
# temp files redirected to drive W: (drive C: is almost full).
#
# Usage:
#   tools\unity\run_unity_batch.ps1 -LogFile <path> [-ProjectPath <path>] [-TimeoutMinutes 60] -UnityArgs @('-executeMethod','Ns.Class.Method')
# Exit code: Unity's exit code, or 124 on timeout (the editor process is then killed).

param(
    [Parameter(Mandatory = $true)][string]$LogFile,
    [string]$ProjectPath = '',
    [string[]]$UnityArgs = @(),
    [int]$TimeoutMinutes = 60
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$unity = 'C:\Program Files\Unity\Hub\Editor\6000.6.0f1\Editor\Unity.exe'

$env:UPM_CACHE_ROOT = Join-Path $root 'Unity\_cache\upm'
$tmp = Join-Path $root 'Unity\_tmp'
$env:TEMP = $tmp
$env:TMP = $tmp
foreach ($dir in $env:UPM_CACHE_ROOT, $tmp, (Split-Path -Parent $LogFile)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

function Quote([string]$s) { if ($s -match '[\s"]') { '"' + ($s -replace '"', '\"') + '"' } else { $s } }

$argList = @('-batchmode', '-logFile', $LogFile)
if ($ProjectPath) { $argList += @('-projectPath', $ProjectPath) }
$argList += $UnityArgs
$argString = ($argList | ForEach-Object { Quote $_ }) -join ' '

$started = Get-Date
Write-Output "[run_unity_batch] $unity $argString"
$proc = Start-Process -FilePath $unity -ArgumentList $argString -PassThru -WindowStyle Hidden
$null = $proc.Handle  # required in Windows PowerShell 5.1 so ExitCode is populated
$finished = $proc.WaitForExit($TimeoutMinutes * 60 * 1000)
if (-not $finished) {
    Stop-Process -Id $proc.Id -Force
    Write-Output "[run_unity_batch] TIMEOUT after $TimeoutMinutes min; editor killed"
    exit 124
}
$elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
Write-Output "[run_unity_batch] exit=$($proc.ExitCode) elapsed=${elapsed}s log=$LogFile"
exit $proc.ExitCode
