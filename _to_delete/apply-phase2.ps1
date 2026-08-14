# Apply the 7 phase-2 files Windows blocked.
#
# Controlled Folder Access (Windows Security -> Ransomware protection) denied
# overwriting these existing files. New files wrote fine, so 21 of 28 are
# already in place; these 7 are staged in _incoming\ waiting to be copied over.
#
# The repo is SAFE as-is: the new files are additive and nothing references
# them until urls.py lands, so the site behaves exactly as it did before.
#
# Run from the repo root:
#     powershell -ExecutionPolicy Bypass -File .\apply-phase2.ps1

$ErrorActionPreference = "Stop"
$files = @(
  "apps\stores\views.py",
  "apps\stores\tests.py",
  "peptidenet\urls.py",
  "README.md",
  "static\css\base.css",
  "templates\themes\base.html",
  "templates\partials\_product_detail.html"
)

$applied = 0
foreach ($f in $files) {
  $src = Join-Path "_incoming" $f
  if (-not (Test-Path $src)) { Write-Host "MISSING  $f" -ForegroundColor Red; continue }
  Copy-Item -Path $src -Destination $f -Force
  Write-Host "applied  $f" -ForegroundColor Green
  $applied++
}

Write-Host ""
Write-Host "$applied of $($files.Count) applied." -ForegroundColor Cyan
Write-Host "Next:"
Write-Host "  python manage.py test          # expect 112 passing"
Write-Host "  git status                     # review, then stage files individually"
Write-Host ""
Write-Host "Then remove the staging folders: _incoming\ and _to_delete\"
