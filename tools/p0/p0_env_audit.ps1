# P0 environment audit: hardware, OS, disks and installed tools.
# Writes docs\p0\env_audit.json and prints a short summary. Read-only.
# Usage: powershell -ExecutionPolicy Bypass -File tools\p0\p0_env_audit.ps1

$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$outJson = Join-Path $root 'docs\p0\env_audit.json'

function Get-FirstLine([string]$exe, [string[]]$exeArgs) {
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $cmd) { return $null }
    $out = & $cmd.Source @exeArgs 2>&1 | Select-Object -First 1
    return ("$out").Trim()
}

$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs = Get-CimInstance Win32_ComputerSystem

$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
    [ordered]@{ name = $_.Name; driverVersion = $_.DriverVersion; driverDate = "$($_.DriverDate)"; videoProcessor = $_.VideoProcessor }
})
$nvsmi = $null
$nvExe = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvExe) {
    $q = & $nvExe.Source --query-gpu=name,driver_version,memory.total,compute_cap,pcie.link.gen.max --format=csv,noheader 2>&1
    $nvsmi = ("$q").Trim()
}

$disks = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    [ordered]@{ drive = $_.DeviceID; freeGB = [math]::Round($_.FreeSpace / 1GB, 1); sizeGB = [math]::Round($_.Size / 1GB, 1) }
})

# Blender (the running instance is the authoring tool)
$blender = Get-Process blender -ErrorAction SilentlyContinue | Select-Object -First 1
$blenderInfo = $null
if ($blender) {
    $blenderInfo = [ordered]@{ path = $blender.Path; productVersion = $blender.MainModule.FileVersionInfo.ProductVersion; windowTitle = $blender.MainWindowTitle }
}

# Unity Hub and editors
$hubExe = 'W:\Unity\Unity Hub\Unity Hub.exe'
$editorRoot = 'C:\Program Files\Unity\Hub\Editor'
$editors = @(Get-ChildItem $editorRoot -Directory | ForEach-Object {
    $exe = Join-Path $_.FullName 'Editor\Unity.exe'
    $pe = Join-Path $_.FullName 'Editor\Data\PlaybackEngines'
    [ordered]@{
        version = $_.Name
        exe = $exe
        productVersion = (Get-Item $exe).VersionInfo.ProductVersion
        playbackEngines = @(Get-ChildItem $pe -Directory | Select-Object -ExpandProperty Name)
        windowsVariations = @(Get-ChildItem (Join-Path $pe 'windowsstandalonesupport\Variations') -Directory | Select-Object -ExpandProperty Name)
        templates = @(Get-ChildItem (Join-Path $_.FullName 'Editor\Data\Resources\PackageManager\ProjectTemplates') -Filter '*.tgz' | Select-Object -ExpandProperty Name)
    }
})

# Visual Studio (needed for IL2CPP; Burst AOT for Windows desktop ships its own linker)
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
$vs = @()
if (Test-Path $vswhere) {
    $vsJson = & $vswhere -all -products * -format json -utf8 | Out-String | ConvertFrom-Json
    foreach ($inst in $vsJson) {
        $vc = & $vswhere -all -products * -path $inst.installationPath -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        $vs += [ordered]@{
            displayName = $inst.displayName
            version = $inst.installationVersion
            path = $inst.installationPath
            vcToolsX64 = [bool]$vc
        }
    }
}
$winSdks = @(Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\Include' -Directory | Select-Object -ExpandProperty Name)

$git = Get-Command git -ErrorAction SilentlyContinue
$ue = 'W:\Unreal Engine 5\UE_5.8'
$ueVersion = $null
if (Test-Path "$ue\Engine\Build\Build.version") {
    $b = Get-Content "$ue\Engine\Build\Build.version" -Raw | ConvertFrom-Json
    $ueVersion = "$($b.MajorVersion).$($b.MinorVersion).$($b.PatchVersion)"
}
$godot = @(Get-Command godot* -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)

$audit = [ordered]@{
    timestamp = (Get-Date).ToString('s')
    os = [ordered]@{ caption = $os.Caption; version = $os.Version; build = $os.BuildNumber }
    cpu = [ordered]@{ name = $cpu.Name.Trim(); cores = $cpu.NumberOfCores; logical = $cpu.NumberOfLogicalProcessors; maxClockMHz = $cpu.MaxClockSpeed; l3KB = $cpu.L3CacheSize }
    ramGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    gpus = $gpus
    nvidiaSmi = $nvsmi
    disks = $disks
    blender = $blenderInfo
    unityHub = [ordered]@{ exe = $hubExe; version = (Get-Item $hubExe).VersionInfo.ProductVersion }
    unityEditors = $editors
    visualStudio = $vs
    windowsSdks = $winSdks
    dotnetSdks = @(& dotnet --list-sdks 2>&1 | ForEach-Object { "$_".Trim() })
    python = Get-FirstLine 'python' @('--version')
    uv = Get-FirstLine 'uv' @('--version')
    git = [ordered]@{ path = $(if ($git) { $git.Source } else { $null }); version = Get-FirstLine 'git' @('--version') }
    vscode = Get-FirstLine 'code' @('--version')
    unrealEngine = [ordered]@{ path = $ue; present = (Test-Path $ue); version = $ueVersion }
    godot = $godot
}

New-Item -ItemType Directory -Force -Path (Split-Path $outJson) | Out-Null
$audit | ConvertTo-Json -Depth 6 | Set-Content -Path $outJson -Encoding UTF8
$audit | ConvertTo-Json -Depth 6
