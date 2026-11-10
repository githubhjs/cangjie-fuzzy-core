param(
  [Parameter(Mandatory = $true)][string]$Wrapper,    # install.ps1 of a typo-tolerant-by-default project, copied to this machine
  [string]$Range = 'normal',
  [string]$FirstSchema = 'cangjie3_fuzzy'
)
# The one-line install path: the wrapper runs as a script block (like `irm URL | iex`), downloads the base installer from GitHub,
# checks the pinned SHA-256, installs into a throwaway Rime folder, then the headless engine test runs on it.
$ErrorActionPreference = 'Stop'
$base = Join-Path $env:TEMP 'cj-online'
if (Test-Path $base) { Remove-Item $base -Recurse -Force }
New-Item -ItemType Directory -Path $base | Out-Null
"PowerShell $($PSVersionTable.PSVersion)"
$src = [IO.File]::ReadAllText($Wrapper)
& ([scriptblock]::Create($src)) -RimeDir "$base\rime" -NoDeploy -SkipWeaselInstall -Cangjie5 -FuzzyRange $Range 2>&1 | Select-String 'downloading|files come|ERROR|installed: cangjie3_fuzzy' | ForEach-Object { $_.Line }
$w = (Get-ChildItem 'C:\Program Files\Rime' -Directory -Filter 'weasel-*' | Sort-Object Name | Select-Object -Last 1).FullName
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = 'C:\Python313\python.exe' }
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& $py (Join-Path $here 'cj_headless.py') --lib "$w\rime.dll" --user "$base\rime" --shared "$w\data" --gens 3,5 --range $Range --require cangjie3_fluency,cangjie3_fuzzy --first-schema $FirstSchema
exit $LASTEXITCODE
