# Runs a Hellcat player build with arguments and waits (timeout). Example:
#   & tools\run_player.ps1 -Exe Builds\P05_Slice\HellcatSlice.exe -LogFile docs\p05\logs\run.log -PlayerArgs @('-scenario','wall','-out','sim\cache\P05')
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][string]$LogFile,
    [string[]]$PlayerArgs = @(),
    [switch]$Windowed,
    [int]$TimeoutMinutes = 20
)
$ErrorActionPreference = 'Stop'
function Quote([string]$s) { if ($s -match '[\s"]') { '"' + ($s -replace '"', '\"') + '"' } else { $s } }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogFile) | Out-Null
$argList = @()
if (-not $Windowed) { $argList += '-batchmode' }
$argList += @('-logFile', $LogFile)
$argList += $PlayerArgs
$argString = ($argList | ForEach-Object { Quote $_ }) -join ' '
$started = Get-Date
Write-Output "[run_player] $Exe $argString"
$proc = Start-Process -FilePath $Exe -ArgumentList $argString -PassThru
$null = $proc.Handle
if (-not $proc.WaitForExit($TimeoutMinutes * 60 * 1000)) {
    Stop-Process -Id $proc.Id -Force
    Write-Output "[run_player] TIMEOUT after $TimeoutMinutes min; killed"
    exit 124
}
$elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
Write-Output "[run_player] exit=$($proc.ExitCode) elapsed=${elapsed}s"
exit $proc.ExitCode
