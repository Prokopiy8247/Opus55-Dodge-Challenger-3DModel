# P7 entry point (brief 14 G-Build): the standalone sandbox Builds\HellcatSandbox\HellcatSandbox.exe (optionally rebuilt),
# then its checks in the player:
#   controls     -scenario controls (virtual keyboard + gamepad; every default control)      -> docs\p7\controls
#   drive        -scenario drive, 300 s on the east loop, 1600x900 window (G-Drive in the sandbox) -> docs\p7\drive
#   drive1440    -scenario drive, 100 s at 2560x1440 borderless full screen (frame rate there)  -> docs\p7\drive1440
#   determinism  -scenario S1 at 50 km/h: the end state must equal the P6 run's (sim\cache\S1\kmh50) -> docs\p7\s1_50
#   mapcheck     -scenario mapcheck (G-Map evidence on the final build)                       -> docs\p5\mapcheck
#   capture      -scenario showcase at 2560x1440 borderless full screen, encoded to docs\video_assets\P7
# and the gate tools\gate_p7.py.
#   & tools\p7\run_p7.ps1 [-Build] [-Only controls,drive,drive1440,determinism,mapcheck,capture]
param(
    [switch]$Build,
    [string[]]$Only = @('controls', 'drive', 'drive1440', 'determinism', 'mapcheck', 'capture')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$logs = "$root\docs\p7\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$exe = "$root\Builds\HellcatSandbox\HellcatSandbox.exe"
$py = "$root\tools\.venv\Scripts\python.exe"
if ($Build) {
    & "$root\tools\unity\run_unity_batch.ps1" -LogFile "$logs\build_sandbox.log" -ProjectPath "$root\Unity\HellcatSandbox" -TimeoutMinutes 60 `
        -UnityArgs @('-executeMethod', 'Hellcat.EditorTools.Build.BuildTasks.BuildSandbox') | Out-Null
    $code = $LASTEXITCODE
    Select-String -Path "$logs\build_sandbox.log" -Pattern 'error CS|\[BuildTasks\]' | ForEach-Object { $_.Line }
    if ($code -ne 0) { "BUILD FAILED ($code)"; exit 1 }
}
$window = @('-screen-fullscreen', '0', '-screen-width', '1600', '-screen-height', '900')
$full = @('-screen-fullscreen', '1', '-window-mode', 'borderless', '-screen-width', '2560', '-screen-height', '1440')

function Run([string]$name, [string[]]$a, [int]$minutes = 30) {
    $t = Get-Date
    & "$root\tools\run_player.ps1" -Exe $exe -LogFile "$logs\$name.log" -Windowed -TimeoutMinutes $minutes -PlayerArgs $a | Out-Null
    "${name}: exit $LASTEXITCODE, $([math]::Round(((Get-Date) - $t).TotalSeconds)) s"
}

if ($Only -contains 'controls') {
    Run 'controls' (@('-scenario', 'controls', '-controlsOut', "$root\docs\p7\controls") + $window) 10
    $j = Get-Content "$root\docs\p7\controls\controls_check.json" -Raw | ConvertFrom-Json
    "  controls: $($j.passed) passed, $($j.failed) failed"
}
if ($Only -contains 'drive') {
    Run 'drive' (@('-scenario', 'drive', '-driveOut', "$root\docs\p7\drive", '-driveSeconds', '300', '-driveRecord', '60') + $window) 20
    Copy-Item "$logs\drive.log" "$root\docs\p7\drive\player.log" -Force
}
if ($Only -contains 'drive1440') {
    Run 'drive1440' (@('-scenario', 'drive', '-driveOut', "$root\docs\p7\drive1440", '-driveSeconds', '100', '-driveRecord', '20') + $full) 15
    Copy-Item "$logs\drive1440.log" "$root\docs\p7\drive1440\player.log" -Force
}
if ($Only -contains 'determinism') {
    $dir = "$root\docs\p7\s1_50"
    Run 'determinism' (@('-scenario', 'S1', '-targetKmh', '50', '-out', $dir, '-capture', '1', '-screen-width', '1280', '-screen-height', '720')) 20
    $a = Get-Content "$dir\S1_50kmh_result.json" -Raw | ConvertFrom-Json
    $b = Get-Content "$root\sim\cache\S1\kmh50\S1_50kmh_result.json" -Raw | ConvertFrom-Json
    "  S1 50 in the sandbox: state $($a.run_state_hash) vs P6 $($b.run_state_hash): $(if ($a.run_state_hash -eq $b.run_state_hash) { 'identical' } else { 'DIFFERENT' })"
}
if ($Only -contains 'mapcheck') {
    Run 'mapcheck' (@('-scenario', 'mapcheck', '-mapOut', "$root\docs\p5\mapcheck") + $window) 40
    & $py "$root\tools\p5\annotate_map.py"
}
if ($Only -contains 'capture') {
    $cap = "$root\docs\p7\capture"
    Run 'capture' (@('-scenario', 'showcase', '-captureOut', $cap) + $full) 60
    & $py "$root\tools\p7\encode_p7.py"
}
& $py "$root\tools\gate_p7.py"
