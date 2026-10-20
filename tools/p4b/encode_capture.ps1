# Encodes the P4b short capture (HellcatDrive.exe -scenario showcase) into docs\p4b\capture\p4b_showcase.mp4
# (H.264, 60 fps, CRF 19, faststart) and writes a contact sheet of 8 frames (p4b_showcase_sheet.jpg).
#   & tools\p4b\encode_capture.ps1 [-Dir docs\p4b\capture]
param([string]$Dir = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Dir) { $Dir = Join-Path $root 'docs\p4b\capture' }
$frames = Join-Path $Dir 'frames'
$n = (Get-ChildItem $frames -Filter 'f_*.jpg').Count
if ($n -eq 0) { throw "no frames in $frames" }
$mp4 = Join-Path $Dir 'p4b_showcase.mp4'
& ffmpeg -y -loglevel error -framerate 60 -i (Join-Path $frames 'f_%05d.jpg') -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -movflags +faststart $mp4
if ($LASTEXITCODE -ne 0) { throw "ffmpeg failed ($LASTEXITCODE)" }
$sheet = Join-Path $Dir 'p4b_showcase_sheet.jpg'
$step = [math]::Max(1, [math]::Floor($n / 8))
& ffmpeg -y -loglevel error -i (Join-Path $frames 'f_%05d.jpg') -vf "select='not(mod(n\,$step))',scale=640:-1,tile=4x2" -frames:v 1 -q:v 3 $sheet
"{0}: {1} frames, {2:N1} s, {3:N1} MB" -f $mp4, $n, ($n / 60.0), ((Get-Item $mp4).Length / 1MB)
