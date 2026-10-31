param(
    [Parameter(Mandatory=$true)][string]$Elf,
    [Parameter(Mandatory=$true)][string]$Pcsx2,
    [Parameter(Mandatory=$true)][string]$BiosDirectory,
    [Parameter(Mandatory=$true)][string]$BiosFilename,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateRange(1,60)][int]$TimeoutSeconds = 45,
    [ValidateSet('POPS_IOP_BINDING','POPS_TRAMPOLINE','POPS_STARTUP_ARGS')][string]$ResultPrefix = 'POPS_IOP_BINDING'
)
$ErrorActionPreference = 'Stop'
$Elf = (Resolve-Path -LiteralPath $Elf).Path
$Pcsx2 = (Resolve-Path -LiteralPath $Pcsx2).Path
$BiosDirectory = (Resolve-Path -LiteralPath $BiosDirectory).Path
$biosPath = Join-Path $BiosDirectory $BiosFilename
if (-not (Test-Path -LiteralPath $biosPath)) { throw 'Existing user-supplied BIOS missing' }
if ($ResultPrefix -eq 'POPS_TRAMPOLINE') {
    & python (Join-Path $PSScriptRoot 'prepare_pops_trampoline_probe.py') --verify-parent $Elf
    if ($LASTEXITCODE -ne 0) { throw 'Trampoline parent overlaps its child destination or staging' }
}
if ($ResultPrefix -eq 'POPS_STARTUP_ARGS') {
    & python (Join-Path $PSScriptRoot 'prepare_pops_startup_args_probe.py') --verify-probe $Elf
    if ($LASTEXITCODE -ne 0) { throw 'Startup parser probe overlaps original regions' }
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Use a fresh output directory' }
New-Item -ItemType Directory -Force "$OutputDirectory\PCSX2\inis" | Out-Null
$ini = @"
[UI]
SettingsVersion = 1
SetupWizardIncomplete = false
ConfirmShutdown = false
PauseOnFocusLoss = false
[Folders]
Bios = $BiosDirectory
[Filenames]
BIOS = $BiosFilename
[MemoryCards]
Slot1_Enable = false
Slot2_Enable = false
[EmuCore/GS]
Renderer = 13
[SPU2/Output]
OutputModule = nullout
[Logging]
EnableFileLogging = true
EnableTimestamps = true
EnableEEConsole = true
EnableIOPConsole = true
"@
[IO.File]::WriteAllText("$OutputDirectory\PCSX2\inis\PCSX2.ini", $ini)
$log = Join-Path $OutputDirectory 'emulog.txt'
$arguments = @('-nogui', '-batch', '-datapath', ('"{0}"' -f $OutputDirectory),
    '-logfile', ('"{0}"' -f $log), '-elf', ('"{0}"' -f $Elf))
$process = Start-Process -FilePath $Pcsx2 -ArgumentList $arguments -WindowStyle Hidden -PassThru
$passed = $false
$lines = @()
try {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $log) {
            $stream = [IO.File]::Open($log, [IO.FileMode]::Open,
                [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            $reader = New-Object IO.StreamReader($stream)
            try { $content = $reader.ReadToEnd() } finally { $reader.Dispose() }
            $lines = @($content -split "`r?`n" | Where-Object { $_.Contains($ResultPrefix) })
            if ($content.Contains($ResultPrefix + '_FAIL')) { break }
            if ($content.Contains($ResultPrefix + '_PASS')) { $passed = $true; break }
        }
        if ($process.HasExited) { break }
        Start-Sleep -Milliseconds 250
    }
} finally {
    # Stop only this isolated probe. It sleeps after reporting its result.
    if (-not $process.HasExited) { Stop-Process -Id $process.Id; $process.WaitForExit() }
}
$result = [ordered]@{
    passed = $passed
    elf_sha256 = (Get-FileHash -LiteralPath $Elf -Algorithm SHA256).Hash.ToLower()
    pcsx2_version = (Get-Item -LiteralPath $Pcsx2).VersionInfo.FileVersion
    bios_sha256 = (Get-FileHash -LiteralPath $biosPath -Algorithm SHA256).Hash.ToLower()
    observations = $lines
    scope = 'Real Sony IOP image/IOPCD, actual SIF RPC and production bridge IRXs; backing medium is controlled IOP memory; no game or physical persistence'
}
if ($ResultPrefix -eq 'POPS_TRAMPOLINE') {
    $result.scope = 'Production trampoline and real EE kernel ExecPS2 with an owned child; no Sony core, foreign IOP, game or save inputs'
}
if ($ResultPrefix -eq 'POPS_STARTUP_ARGS') {
    $result.scope = 'Original Sony parser prefix and original string routine; modeled init and stop services; no full Sony startup, game or save acceptance'
}
$result | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'result.json')
$lines | Write-Output
if (-not $passed) { throw "No $ResultPrefix success marker: $log" }
