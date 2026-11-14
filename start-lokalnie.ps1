$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "  FASARO Zlecenia - podglad lokalny" -ForegroundColor Yellow
Write-Host "  =================================" -ForegroundColor DarkYellow
Write-Host ""

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Nie znaleziono Pythona." -ForegroundColor Red
    Write-Host "Zainstaluj Python 3.12 z https://www.python.org/downloads/"
    Write-Host "Podczas instalacji zaznacz opcje 'Add python.exe to PATH'."
    Read-Host "Nacisnij Enter, aby zamknac"
    exit 1
}

$port = 8765
$docs = Join-Path $root "docs"

if (-not (Test-Path $docs)) {
    Write-Host "Brak folderu docs - pliki projektu sa niekompletne." -ForegroundColor Red
    Read-Host "Nacisnij Enter, aby zamknac"
    exit 1
}

Write-Host "Otwieram http://localhost:$port/ ..." -ForegroundColor Green
Start-Process "http://localhost:$port/"

Write-Host ""
Write-Host "Serwer dziala. Zostaw to okno otwarte." -ForegroundColor Green
Write-Host "Zamkniecie okna zatrzymuje serwer."
Write-Host ""

python -m http.server $port --directory $docs
