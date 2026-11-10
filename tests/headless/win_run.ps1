param(
  [Parameter(Mandatory = $true)][string]$Zip,        # full release zip already copied to this machine
  [string]$Range = 'normal',                          # narrow | normal | wide
  [string]$InstallArgs = '',                          # extra installer arguments, e.g. "-FuzzyDefault"
  [string]$Gens = '3,5',
  [string]$FirstSchema = ''                           # the schema that must be first in schema_list
)
# Installs the release bundle into a throwaway Rime folder with Windows PowerShell 5.1 and runs the headless engine test
# with Weasel's own rime.dll. Needs Weasel (C:\Program Files\Rime\weasel-*) and Python 3 on the machine.
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:TEMP 'cj-headless'
if (Test-Path $base) { Remove-Item $base -Recurse -Force }
New-Item -ItemType Directory -Path $base | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::ExtractToDirectory($Zip, "$base\bundle")
$inst = Get-ChildItem "$base\bundle" -Recurse -Filter install.ps1 | Select-Object -First 1
"PowerShell $($PSVersionTable.PSVersion)"
$argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $inst.FullName, '-Offline', '-NoDeploy', '-SkipWeaselInstall', '-RimeDir', "$base\rime", '-FuzzyRange', $Range)
if ($Gens -match '5') { $argList += '-Cangjie5' }
if ($InstallArgs) { $argList += ($InstallArgs -split ' ') }
& powershell @argList 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { "INSTALLER FAILED rc=$LASTEXITCODE"; exit 2 }
$w = (Get-ChildItem 'C:\Program Files\Rime' -Directory -Filter 'weasel-*' | Sort-Object Name | Select-Object -Last 1).FullName
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = 'C:\Python313\python.exe' }
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$fs = @()
if ($FirstSchema) { $fs = @('--first-schema', $FirstSchema) }
& $py (Join-Path $here 'cj_headless.py') --lib "$w\rime.dll" --user "$base\rime" --shared "$w\data" --gens $Gens --range $Range --require cangjie3_fluency,cangjie3_fuzzy @fs
exit $LASTEXITCODE
