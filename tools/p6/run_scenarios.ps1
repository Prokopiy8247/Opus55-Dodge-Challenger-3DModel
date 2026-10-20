# P6 scenario runs on the test map (brief 9): optional test-map player build, then the scripted scenarios S1-S8
# (CarCrashScenario: metrics, the input recording, captures, the replay check and the slow-motion variant) and their
# driven variants (DrivenScenario: teleport with the speed hold, F5 / F6); one summary line per run from its result JSON.
# Each run is 'scenario:km/h:folder[:extra player arguments]', written to sim\cache\<scenario>\<folder>; a folder ending
# in 'driven' runs the driven variant (-driven 1).
# Example:
#   & tools\p6\run_scenarios.ps1 -Build -Runs 'S1:50:kmh50','S8:120:kmh120'
param(
    [string[]]$Runs = @('S1:50:kmh50'),
    [switch]$Build,
    [switch]$Capture,
    [string]$Tag = 'p6',
    [int]$TimeoutMinutes = 40
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$unity = "$root\tools\unity\run_unity_batch.ps1"
$project = "$root\Unity\HellcatSandbox"
$logs = "$root\docs\p6\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if ($Build) {
    & $unity -LogFile "$logs\build_$Tag.log" -ProjectPath $project -TimeoutMinutes 60 `
        -UnityArgs @('-executeMethod', 'Hellcat.EditorTools.Build.BuildTasks.BuildTestMap') | Out-Null
    $code = $LASTEXITCODE
    Select-String -Path "$logs\build_$Tag.log" -Pattern 'error CS|\[BuildTasks\]' | ForEach-Object { $_.Line }
    if ($code -ne 0) { "BUILD FAILED ($code)"; exit 1 }
}
$exe = "$root\Builds\TestMap\HellcatTestMap.exe"
foreach ($run in $Runs) {
    $f = $run.Split(':', 4)
    $sc, $k, $folder = $f[0], $f[1], $f[2]
    $extra = if ($f.Count -gt 3 -and $f[3]) { $f[3].Split(' ', [StringSplitOptions]::RemoveEmptyEntries) } else { @() }
    $dir = "$root\sim\cache\$sc\$folder"
    foreach ($sub in 'frames', 'frames_slowmo') { if (Test-Path "$dir\$sub") { Remove-Item -Recurse -Force "$dir\$sub" } }
    $driven = $folder -like '*driven*'
    $a = @('-scenario', $sc, '-targetKmh', $k, '-out', $dir, '-screen-width', '1280', '-screen-height', '720')
    if ($driven) { $a += @('-driven', '1') } else { $a += @('-capture', $(if ($Capture) { '1' } else { '0' })) }
    $a += $extra
    $started = Get-Date
    & "$root\tools\run_player.ps1" -Exe $exe -LogFile "$logs\${Tag}_${sc}_$folder.log" -Windowed -TimeoutMinutes $TimeoutMinutes -PlayerArgs $a | Out-Null
    $secs = [math]::Round(((Get-Date) - $started).TotalSeconds)
    if ($driven) {
        $jf = "$dir\$($sc)_$($k)kmh_driven.json"
        if (-not (Test-Path $jf)) { "$sc ${folder}: NO RESULT (${secs}s)"; continue }
        $j = Get-Content $jf -Raw | ConvertFrom-Json
        "$sc ${folder}: released $($j.release_kmh) km/h ($($j.release)) broken $($j.broken_beams) deform $($j.max_deformation_m) " +
        "det $($j.detached_parts -join '+') replay $($j.replay_identical) frames $($j.recording_frames) (${secs}s)"
        continue
    }
    $jf = "$dir\$($sc)_$($k)kmh_result.json"
    if (-not (Test-Path $jf)) { "$sc ${folder}: NO RESULT (${secs}s)"; continue }
    $j = Get-Content $jf -Raw | ConvertFrom-Json
    "$sc ${folder}: entry $($j.entry_speed_kmh) impact $($j.speed_at_impact_kmh) crush $($j.dynamic_crush_m)/$($j.residual_crush_m) " +
    "deform $($j.max_deformation_m) peak4 $($j.peak_cabin_decel_g_4ms)/$($j.peak_cabin_accel_g_4ms) pulse $($j.pulse_duration_ms) " +
    "broken $($j.broken_beams) Wpl $($j.energy_J.plastic) det $($j.detached_parts -join '+') created $($j.energy_created_J) " +
    "tun $($j.tunnelled_nodes_max) air $($j.airborne_s) props $($j.props_moved) replay $($j.replay_identical) " +
    "frames $($j.frames_captured)/$($j.slowmo_frames) us $($j.physics_us_per_substep) (${secs}s)"
}
