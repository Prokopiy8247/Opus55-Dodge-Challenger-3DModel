# P4 end-to-end re-run after a skeleton or solver change: car import, crash player build, the crash series
# (tools/p4/crash_series.ps1), the X21 crash diagnostic, the P3 suite (T1-T8, E1, D1) and the P3b suite (T9-T14).
# Prints the series summary lines and the suites' per-test verdicts. Example:
#   & tools\p4\pipeline.ps1 -Tag final3
param([string]$Tag = 'pipeline', [switch]$SkipSeries, [switch]$SkipSuites)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$u = "$root\tools\unity\run_unity_batch.ps1"
$proj = "$root\Unity\HellcatSandbox"
if (-not $SkipSeries) {
    & "$root\tools\p4\crash_series.ps1" -Import -Build -Tag $Tag
}
if (-not $SkipSuites) {
    $runs = @(
        @("$root\docs\p4\logs\x21_$Tag.log", @('-executeMethod', 'Hellcat.EditorTools.Validation.ValidationTasks.RunDynamics', '-valTests', 'X21', '-valOut', "$root\docs\p4\x21")),
        @("$root\docs\p3\logs\suite_$Tag.log", @('-executeMethod', 'Hellcat.EditorTools.Validation.ValidationTasks.RunAll')),
        @("$root\docs\p3b\logs\suite_$Tag.log", @('-executeMethod', 'Hellcat.EditorTools.Validation.ValidationTasks.RunDynamics'))
    )
    foreach ($r in $runs) {
        $started = Get-Date
        & $u -LogFile $r[0] -ProjectPath $proj -TimeoutMinutes 120 -UnityArgs $r[1] | Out-Null
        $min = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
        "== $(Split-Path -Leaf $r[0]) ($min min)"
        Select-String -Path $r[0] -Pattern '\[Validation\] [TXDE][0-9]+: |\[ValidationTasks\]|error CS' | ForEach-Object { $_.Line }
    }
}
