# P6 entry point (brief 17): the test-map player build, then every scenario run of the gate - the eight scenarios at the
# brief's speeds with captures and the slow-motion replay, the speed series without captures, the glass swap test and the
# driven variants - and the gate (tools/gate_p6.py). The sensitivity sweep is tools/p6/sweep.py, the videos
# tools/p6/make_videos.py.
#   & tools\p6\run_all_p6.ps1 [-NoBuild] [-Only captured,series,glass,driven]
param(
    [switch]$NoBuild,
    [string[]]$Only = @('captured', 'series', 'glass', 'driven')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$run = "$root\tools\p6\run_scenarios.ps1"
$captured = @('S1:50:kmh50', 'S2:64:kmh64', 'S3:50:kmh50', 'S4:40:kmh40', 'S5:80:kmh80', 'S6:70:kmh70', 'S7:15:kmh15', 'S8:120:kmh120')
$series = @('S1:30:kmh30', 'S1:40:kmh40', 'S1:56:kmh56', 'S1:64:kmh64', 'S2:40:kmh40', 'S2:56:kmh56', 'S3:30:kmh30', 'S3:40:kmh40',
            'S4:30:kmh30', 'S4:50:kmh50', 'S5:60:kmh60', 'S5:70:kmh70', 'S6:50:kmh50', 'S6:60:kmh60', 'S7:10:kmh10', 'S7:20:kmh20')
$driven = @('S1:50:driven', 'S2:64:driven', 'S3:50:driven', 'S4:40:driven', 'S5:80:driven', 'S6:70:driven', 'S7:15:driven', 'S8:120:driven')
$first = -not $NoBuild
if ($Only -contains 'captured') { & $run -Build:$first -Capture -Tag p6cap -Runs $captured; $first = $false }
if ($Only -contains 'series') { & $run -Build:$first -Tag p6ser -Runs $series; $first = $false }
if ($Only -contains 'glass') { & $run -Build:$first -Capture -Tag p6glass -Runs @('S8:120:kmh120_glasstest:-breakGlass 0.4 -slowmo 0'); $first = $false }
if ($Only -contains 'driven') { & $run -Build:$first -Tag p6drv -Runs $driven; $first = $false }
& "$root\tools\.venv\Scripts\python.exe" "$root\tools\gate_p6.py"
