[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateRange(1, 16)]
    [int] $StartLevel,

    [Parameter(Position = 1)]
    [ValidateRange(1, 16)]
    [int] $EndLevel = 0,

    [string] $BackendDirectory = "/home/gchichester/code/pailin-abroad/backend",

    [switch] $SkipParse,
    [switch] $SkipImport,
    [switch] $SkipThai,
    [switch] $SkipEnglish
)

$ErrorActionPreference = "Stop"

if ($EndLevel -ne 0 -and $EndLevel -lt $StartLevel) {
    throw "EndLevel must be greater than or equal to StartLevel."
}

if (-not ("PailinImportPowerRequest" -as [type])) {
    Add-Type @"
using System.Runtime.InteropServices;

public static class PailinImportPowerRequest
{
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint flags);
}
"@
}

$ES_CONTINUOUS = [uint32] 2147483648
$ES_SYSTEM_REQUIRED = [uint32] 1
$keepAwakeFlags = [uint32] 2147483649

$pythonPath = "$BackendDirectory/venv/bin/python"
$importerArguments = @(
    "--cd", $BackendDirectory,
    "--",
    $pythonPath,
    "-m", "app.tools.level_doc_handler",
    $StartLevel.ToString()
)

if ($EndLevel -ne 0) {
    $importerArguments += $EndLevel.ToString()
}
if ($SkipParse) {
    $importerArguments += "--skip-parse"
}
if ($SkipImport) {
    $importerArguments += "--skip-import"
}
if ($SkipThai) {
    $importerArguments += "--skip-th"
}
if ($SkipEnglish) {
    $importerArguments += "--skip-en"
}

$powerRequestActive = $false
$exitCode = 1

try {
    $previousState = [PailinImportPowerRequest]::SetThreadExecutionState($keepAwakeFlags)
    if ($previousState -eq 0) {
        $win32Error = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "Windows rejected the system power request (Win32 error $win32Error)."
    }

    $powerRequestActive = $true
    Write-Host "Windows sleep blocked for this import; the display may still turn off."
    Write-Host "Starting Pailin importer for level $StartLevel$(if ($EndLevel -ne 0) { " through $EndLevel" })..."

    & wsl.exe @importerArguments
    $exitCode = $LASTEXITCODE
}
finally {
    if ($powerRequestActive) {
        [void] [PailinImportPowerRequest]::SetThreadExecutionState($ES_CONTINUOUS)
        Write-Host "Windows sleep block released."
    }
}

exit $exitCode
