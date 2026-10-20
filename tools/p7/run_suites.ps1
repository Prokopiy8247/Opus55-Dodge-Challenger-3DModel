# P7: every earlier gate's evidence re-run on the final code and vehicle data (brief 14: gates before every checkpoint):
#   p3       validation suite tests 1-8, E1, D1 (ValidationTasks.RunAll)            -> docs\p3\validation
#   p3b      dynamics suite tests 9-14 (ValidationTasks.RunDynamics)                 -> docs\p3b\validation
#   t15      record / replay determinism (ValidationTasks.RunGame)                   -> docs\p4b\validation
#   drive    the P4b drive player rebuilt, its 5-minute G-Drive test (977 m loop)    -> docs\p4b\drive
#   gates    gate_p2, gate_p3, gate_p3b, gate_p4b, gate_p5, gate_p6 (and the reports of P3 / P3b regenerated)
# Run alone (no other Unity or player job): the suites measure the solver's speed.
#   & tools\p7\run_suites.ps1 [-Only p3,p3b,t15,drive,gates]
param([string[]]$Only = @('p3', 'p3b', 't15', 'drive', 'gates'))
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$unity = "$root\tools\unity\run_unity_batch.ps1"
$project = "$root\Unity\HellcatSandbox"
$logs = "$root\docs\p7\logs"
$py = "$root\tools\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Batch([string]$name, [string[]]$a, [int]$minutes = 90) {
    $t = Get-Date
    & $unity -LogFile "$logs\$name.log" -ProjectPath $project -TimeoutMinutes $minutes -UnityArgs $a | Out-Null
    "${name}: exit $LASTEXITCODE, $([math]::Round(((Get-Date) - $t).TotalMinutes, 1)) min"
}

if ($Only -contains 'p3') { Batch 'suite_p3' @('-executeMethod', 'Hellcat.EditorTools.Validation.ValidationTasks.RunAll') }
if ($Only -contains 'p3b') { Batch 'suite_p3b' @('-executeMethod', 'Hellcat.EditorTools.Validation.ValidationTasks.RunDynamics', '-valTests', 'T9,T10,T11,T12,T13,T14') }
if ($Only -contains 't15') { Batch 'suite_t15' @('-executeMethod', 'Hellcat.EditorTools.Validation.ValidationTasks.RunGame') }
if ($Only -contains 'drive') {
    Batch 'build_drive' @('-executeMethod', 'Hellcat.EditorTools.Build.BuildTasks.BuildDrive') 60
    $t = Get-Date
    & "$root\tools\run_player.ps1" -Exe "$root\Builds\P4b_Drive\HellcatDrive.exe" -LogFile "$logs\drive_p4b.log" -Windowed -TimeoutMinutes 20 `
        -PlayerArgs @('-scenario', 'drive', '-driveOut', "$root\docs\p4b\drive", '-screen-fullscreen', '0', '-screen-width', '1600', '-screen-height', '900') | Out-Null
    Copy-Item "$logs\drive_p4b.log" "$root\docs\p4b\drive\player.log" -Force
    "drive_p4b: exit $LASTEXITCODE, $([math]::Round(((Get-Date) - $t).TotalMinutes, 1)) min"
}
if ($Only -contains 'gates') {
    & $py -I "$root\tools\p3\make_validation_report.py"
    if (Test-Path "$root\tools\p3b\plots.py") { & $py "$root\tools\p3b\plots.py" }
    if (Test-Path "$root\tools\p3b\make_dynamics_report.py") { & $py "$root\tools\p3b\make_dynamics_report.py" }
    foreach ($g in 'p2', 'p3', 'p3b', 'p4b', 'p5', 'p6') {
        $out = & $py "$root\tools\gate_$g.py" 2>&1
        "gate ${g}: $($out | Select-Object -Last 1)"
    }
}
