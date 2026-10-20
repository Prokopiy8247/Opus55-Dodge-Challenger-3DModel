# Calls a function of the hcar package inside the project Blender through blender_bridge.py.
# Usage: & tools\blender\bcall.ps1 hcar.viewshot:shot @{ path = 'W:/x.png'; distance = 7.5 }
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Target,
    [Parameter(Position = 1)][hashtable]$Arguments = @{},
    [int]$Timeout = 180
)
$tmp = Join-Path $env:TEMP ("hcar_args_{0}.json" -f [guid]::NewGuid().ToString('N'))
try {
    ($Arguments | ConvertTo-Json -Depth 12 -Compress) | Set-Content -Path $tmp -Encoding UTF8
    & python -I (Join-Path $PSScriptRoot 'blender_bridge.py') call $Target --args-file $tmp --timeout $Timeout
    exit $LASTEXITCODE
}
finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
}
