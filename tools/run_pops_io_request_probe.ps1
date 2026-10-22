param(
    [Parameter(Mandatory=$true)][string]$Elf,
    [Parameter(Mandatory=$true)][string]$Pcsx2,
    [Parameter(Mandatory=$true)][string]$BiosDirectory,
    [Parameter(Mandatory=$true)][string]$BiosFilename,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateRange(1,60)][int]$TimeoutSeconds = 45
)
$ErrorActionPreference = 'Stop'
$Elf = (Resolve-Path -LiteralPath $Elf).Path
$Pcsx2 = (Resolve-Path -LiteralPath $Pcsx2).Path
$BiosDirectory = (Resolve-Path -LiteralPath $BiosDirectory).Path
$biosPath = Join-Path $BiosDirectory $BiosFilename
if (-not (Test-Path -LiteralPath $biosPath)) { throw 'Existing user-supplied BIOS missing' }
& python (Join-Path $PSScriptRoot 'prepare_pops_io_request_probe.py') --verify-probe $Elf
if ($LASTEXITCODE -ne 0) { throw 'Original-code injection overlaps probe memory' }
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
            $lines = @($content -split "`r?`n" | Where-Object { $_.Contains('POPS_EE_IO_REQUEST') })
            if ($content.Contains('POPS_EE_IO_REQUEST_FAIL')) { break }
            if ($content.Contains('POPS_EE_IO_REQUEST_PASS')) { $passed = $true; break }
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
    scope = 'Original R5900 FUN_00210090; track/RPC/semaphore/log services are doubles; no physical-console or save result'
}
$result | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $OutputDirectory 'result.json')
$lines | Write-Output
if (-not $passed) { throw "No original EE request success marker: $log" }
