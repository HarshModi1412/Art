# Build, check, preview-snapshot and render one video.
#   powershell -ExecutionPolicy Bypass -File tools\make.ps1 reel-01-drop                    # build + lint
#   powershell -ExecutionPolicy Bypass -File tools\make.ps1 reel-01-drop -At "1,5.5,12"     # + snapshots
#   powershell -ExecutionPolicy Bypass -File tools\make.ps1 reel-01-drop -Render            # + final.mp4 into ready-to-post
param([Parameter(Mandatory = $true)][string]$Name, [string]$At = "", [switch]$Render, [switch]$Draft)

$ErrorActionPreference = "Stop"
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
$env:HYPERFRAMES_PYTHON = "D:\Claude\Extra\tools\kokoro-venv\Scripts\python.exe"
$env:HYPERFRAMES_SKIP_SKILLS = "1"
$root = Split-Path $PSScriptRoot -Parent
$p = Join-Path $root $Name
$hf = "npx --yes hyperframes@0.8.78"

Copy-Item (Join-Path $root "_lib\hyperframes.json") $p -Force
node (Join-Path $root "tools\build.mjs") $p
if ($LASTEXITCODE -ne 0) { throw "build failed" }

cmd /c "$hf lint `"$p`" 2>&1" | Select-String "✗|◇"

if ($At) {
  $snaps = Join-Path $p "snaps"
  if (Test-Path $snaps) { cmd /c "rmdir /s /q `"$snaps`"" }
  cmd /c "$hf snapshot `"$p`" --at $At --no-end --describe false --timeout 30000 -o `"$snaps`" 2>&1" | Select-String "saved|rror"
}

if ($Render) {
  $q = if ($Draft) { "draft" } else { "high" }
  $out = Join-Path $p "final.mp4"
  cmd /c "$hf render `"$p`" --quality $q --output `"$out`" 2>&1" | Select-String "Render complete|rror|video ·"
  if (-not (Test-Path $out)) { throw "render failed" }
  $meta = Get-Content (Join-Path $p "script.json") -Raw | ConvertFrom-Json
  if ($meta.folder) {
    $dest = Join-Path $root "..\..\ready-to-post\$($meta.folder)"
    New-Item -ItemType Directory -Force $dest | Out-Null
    Copy-Item $out (Join-Path $dest "video.mp4") -Force
    if (Test-Path (Join-Path $p "caption.txt")) { Copy-Item (Join-Path $p "caption.txt") $dest -Force }
    Write-Host "-> $dest"
  }
}
