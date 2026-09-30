# Export every US carousel to instagram/ready-to-post/<post folder>/slide-NN.png
#
#   powershell -ExecutionPolicy Bypass -File export.ps1              # all posts
#   powershell -ExecutionPolicy Bypass -File export.ps1 post-03      # one post
#
# App screenshots are read from instagram/screenshots/ on every run, so dropping
# the US sample-shop versions in there (same file names) and re-running is enough.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Posts)
if (-not $Posts) { $Posts = @("post-01", "post-03", "post-07", "post-10", "post-12") }

$ErrorActionPreference = "Stop"
$root   = $PSScriptRoot
$shared = Join-Path $root "_shared"
$shots  = Join-Path $root "..\screenshots"
$ready  = Join-Path $root "..\ready-to-post"
$env:HYPERFRAMES_SKIP_SKILLS = "1"

$catalog = @{
  "post-01" = @{ slides = 6; folder = "W1-Mon - Post 01 - You do 6 peoples jobs" }
  "post-03" = @{ slides = 7; folder = "W1-Tue - Post 03 - More followers fewer orders" }
  "post-12" = @{ slides = 5; folder = "W1-Fri - Post 12 - 0 customers 20 sellers (HOLD)" }
  "post-10" = @{ slides = 4; folder = "W3-Thu - Post 10 - Wrong answers only" }
  "post-07" = @{ slides = 4; folder = "W3-Fri - Post 07 - Warning" }
}

foreach ($p in $Posts) {
  $cfg  = $catalog[$p]
  $proj = Join-Path $root $p
  Write-Host "== $p ($($cfg.slides) slides)"

  Copy-Item (Join-Path $shared "otm.css") $proj -Force
  Copy-Item (Join-Path $shared "hyperframes.json") $proj -Force
  New-Item -ItemType Directory -Force (Join-Path $proj "assets") | Out-Null
  foreach ($f in "app-today.png", "app-sales-top.png", "app-site.png") {
    Copy-Item (Join-Path $shots $f) (Join-Path $proj "assets") -Force
  }

  # one slide per second of timeline; capture the middle of each second
  $at  = ((0..($cfg.slides - 1)) | ForEach-Object { "$($_ + 0.5)" }) -join ","
  $tmp = Join-Path $proj "snapshots"
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  cmd /c "npx --yes hyperframes@0.8.78 snapshot `"$proj`" --at $at --no-end --describe false --timeout 20000 -o `"$tmp`" 2>&1" |
    Where-Object { $_ -match "saved|error|Error|fail" }
  if ($LASTEXITCODE -ne 0) { throw "snapshot failed for $p" }

  $frames = @(Get-ChildItem (Join-Path $tmp "frame-*.png") | Sort-Object Name)
  if ($frames.Count -ne $cfg.slides) { throw "$p expected $($cfg.slides) frames, got $($frames.Count)" }

  $out = Join-Path $ready $cfg.folder
  if (Test-Path $out) { Get-ChildItem $out -Filter "slide-*.png" | Remove-Item -Force }
  New-Item -ItemType Directory -Force $out | Out-Null
  for ($i = 0; $i -lt $frames.Count; $i++) {
    Copy-Item $frames[$i].FullName (Join-Path $out ("slide-{0:D2}.png" -f ($i + 1)))
  }
  Copy-Item (Join-Path $proj "caption.txt") $out -Force
  Write-Host "   -> $out"
}

