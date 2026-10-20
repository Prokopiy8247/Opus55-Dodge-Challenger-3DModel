# P4 crash series: optional car import (Tools/Hellcat/Import Car) and crash player build, then the crash runs with
# frame captures; prints one summary line per run from its result JSON.
# Each run is 'scenario:km/h:folder[:extra player arguments]', written to sim\cache\<scenario>\<folder>.
# Example:
#   & tools\p4\crash_series.ps1 -Import -Build -Runs 'S1:50:kmh50','S8:120:kmh120:-launch 1'
param(
    [string[]]$Runs = @('S1:30:kmh30', 'S1:40:kmh40', 'S1:50:kmh50', 'S1:56:kmh56', 'S1:64:kmh64',
                        'S8:120:kmh120:-launch 1', 'S8:120:kmh120_glasstest:-launch 1 -breakGlass 0.4',
                        'S1:50:kmh50_slowmo:-fps 250 -lead 0.15 -postImpact 0.7'),
    # capture window of the runs without their own -lead / -postImpact: 3 s before the impact, 4 s after (brief 9: 6-10 s)
    [string]$Window = '-lead 3 -postImpact 4',
    [switch]$Import,
    [switch]$Build,
    [string]$Tag = 'series'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$unity = "$root\tools\unity\run_unity_batch.ps1"
$project = "$root\Unity\HellcatSandbox"
$logs = "$root\docs\p4\logs"
if ($Import) {
    & $unity -LogFile "$logs\import_$Tag.log" -ProjectPath $project -TimeoutMinutes 40 `
        -UnityArgs @('-executeMethod', 'Hellcat.EditorTools.Car.CarImporter.ImportBatch') | Out-Null
    Select-String -Path "$logs\import_$Tag.log" -Pattern 'error CS|\[CarImporter\]' | ForEach-Object { $_.Line }
}
if ($Build) {
    & $unity -LogFile "$logs\build_$Tag.log" -ProjectPath $project -TimeoutMinutes 60 `
        -UnityArgs @('-executeMethod', 'Hellcat.EditorTools.Build.BuildTasks.BuildCrash', '-quit') | Out-Null
    Select-String -Path "$logs\build_$Tag.log" -Pattern 'error CS|\[BuildTasks\]' | ForEach-Object { $_.Line }
}
$exe = "$root\Builds\P4_Crash\HellcatCrash.exe"
foreach ($run in $Runs) {
    $f = $run.Split(':', 4)
    $sc, $k, $folder = $f[0], $f[1], $f[2]
    $extra = if ($f.Count -gt 3 -and $f[3]) { $f[3].Split(' ', [StringSplitOptions]::RemoveEmptyEntries) } else { @() }
    if ($Window -and -not ($extra -contains '-lead')) { $extra += $Window.Split(' ', [StringSplitOptions]::RemoveEmptyEntries) }
    $dir = "$root\sim\cache\$sc\$folder"
    if (Test-Path "$dir\frames") { Remove-Item -Recurse -Force "$dir\frames" }    # no frames left over from a longer run
    $a = @('-scenario', $sc, '-targetKmh', $k, '-out', $dir, '-capture', '1', '-screen-width', '1280', '-screen-height', '720') + $extra
    & "$root\tools\run_player.ps1" -Exe $exe -LogFile "$logs\${Tag}_${folder}_$sc.log" -Windowed -TimeoutMinutes 40 -PlayerArgs $a | Out-Null
    $jf = "$dir\$($sc)_$($k)kmh_result.json"
    if (-not (Test-Path $jf)) { "$sc ${folder}: NO RESULT"; continue }
    $j = Get-Content $jf -Raw | ConvertFrom-Json
    "$sc ${folder}: v $($j.speed_at_impact_kmh) crush $($j.dynamic_crush_m)/$($j.residual_crush_m) peak4 $($j.peak_cabin_decel_g_4ms) " +
    "pulse $($j.pulse_duration_ms) reb $($j.rebound_mps) broken $($j.broken_beams) Wpl $($j.energy_J.plastic) " +
    "det $($j.detached_parts -join '+') created $($j.energy_created_J) tun $($j.tunnelled_nodes_max) glass $($j.glass_panes_shattered) " +
    "rot $($j.skin_max_frame_rotation_deg) ($($j.skin_max_frame_rotation_node)) cabInv $($j.skin_cabin_inverted_share) " +
    "hood $($j.hood_rise_m) roof $($j.roof_skin_rise_m) latch $($j.door_latch_broken) frames $($j.frames_captured)"
}
