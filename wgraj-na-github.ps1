$ErrorActionPreference = "Stop"

function Stop-Script {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    Read-Host "Nacisnij Enter, aby zamknac"
    exit 1
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "  FASARO Zlecenia - publikacja na GitHub" -ForegroundColor Yellow
Write-Host "  ======================================" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "Ten skrypt robi wszystko sam:"
Write-Host "  1. loguje do GitHuba,"
Write-Host "  2. tworzy publiczne repozytorium,"
Write-Host "  3. wgrywa pliki,"
Write-Host "  4. wlacza darmowa strone GitHub Pages,"
Write-Host "  5. uruchamia pierwszy skan zlecen."
Write-Host ""

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Stop-Script ("Brak programu GitHub CLI.`n`nZainstaluj go w PowerShell:" +
        "`n    winget install --id GitHub.cli" +
        "`n`nPotem uruchom ten skrypt jeszcze raz.")
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Stop-Script ("Brak programu Git.`n`nZainstaluj go w PowerShell:" +
        "`n    winget install --id Git.Git" +
        "`n`nPotem uruchom ten skrypt jeszcze raz.")
}

# --- Logowanie ---

$authOk = $false
try {
    gh auth status --hostname github.com 2>$null | Out-Null
    $authOk = ($LASTEXITCODE -eq 0)
} catch {
    $authOk = $false
}

if (-not $authOk) {
    Write-Host ""
    Write-Host "  GitHub wymaga jednorazowego zalogowania." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Zaraz zobaczysz kod w formacie ABCD-1234."
    Write-Host "  1. Skopiuj ten kod."
    Write-Host "  2. Nacisnij Enter - otworzy sie przegladarka."
    Write-Host "  3. Wklej kod i kliknij 'Authorize github'."
    Write-Host "  4. Wroc tutaj - logowanie zakonczy sie samo."
    Write-Host ""
    Read-Host "Nacisnij Enter, aby uruchomic logowanie"

    gh auth login --hostname github.com --git-protocol https --web

    $authOk = $false
    try {
        gh auth status --hostname github.com 2>$null | Out-Null
        $authOk = ($LASTEXITCODE -eq 0)
    } catch {
        $authOk = $false
    }

    if (-not $authOk) {
        Stop-Script ("Logowanie nie powiodlo sie.`n`nSprobuj recznie w PowerShell:" +
            "`n    gh auth login --hostname github.com --git-protocol https --web" +
            "`n`nJesli nie masz konta GitHub, zaloz je bezplatnie na https://github.com/signup")
    }
}

$owner = (gh api user --jq ".login").Trim()
if ([string]::IsNullOrWhiteSpace($owner)) {
    Stop-Script "Nie udalo sie odczytac nazwy konta GitHub."
}

# Tozsamosc autora commitow (lokalnie w tym repozytorium).
git config user.name $owner | Out-Null
git config user.email "$owner@users.noreply.github.com" | Out-Null

Write-Host ""
Write-Host "Zalogowano jako: $owner" -ForegroundColor Green
Write-Host ""

# --- Nazwa repozytorium ---

$defaultName = "fasaro-zlecenia"
$repoName = Read-Host "Nazwa repozytorium (Enter = $defaultName)"
if ([string]::IsNullOrWhiteSpace($repoName)) {
    $repoName = $defaultName
}
$repoName = $repoName.Trim()
$full = "$owner/$repoName"

# --- Git: pierwszy commit ---

if (-not (Test-Path (Join-Path $root ".git"))) {
    Write-Host "Inicjuje repozytorium git..." -ForegroundColor Cyan
    git init | Out-Null
}

git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "FASARO Zlecenia - wersja startowa" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-Script "Nie udalo sie zapisac zmian w git."
    }
}
git branch -M main | Out-Null

# --- Repozytorium na GitHubie ---

gh repo view $full 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tworze publiczne repozytorium $full ..." -ForegroundColor Cyan
    gh repo create $full --public --source=. --remote=origin --push
    if ($LASTEXITCODE -ne 0) {
        Stop-Script "Nie udalo sie utworzyc repozytorium. Sprawdz, czy nazwa jest wolna."
    }
} else {
    Write-Host "Repozytorium juz istnieje - dogrywam zmiany..." -ForegroundColor Cyan
    git remote remove origin 2>$null | Out-Null
    git remote add origin "https://github.com/$full.git"
    git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        Stop-Script "Nie udalo sie wgrac plikow do repozytorium."
    }
}

# --- GitHub Pages ---

Write-Host "Wlaczam GitHub Pages (folder docs)..." -ForegroundColor Cyan
$pagesBody = '{"source":{"branch":"main","path":"/docs"}}'

$pagesBody | gh api -X POST "repos/$full/pages" --input - 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    $pagesBody | gh api -X PUT "repos/$full/pages" --input - 2>$null | Out-Null
}

if ($repoName -eq "$owner.github.io") {
    $url = "https://$owner.github.io/"
} else {
    $url = "https://$owner.github.io/$repoName/"
}

# --- Pierwszy skan ---

Write-Host "Uruchamiam pierwszy skan (moze potrwac 2-3 minuty)..." -ForegroundColor Cyan
Start-Sleep -Seconds 3
gh workflow run skan.yml --repo $full 2>$null | Out-Null

# --- Podsumowanie ---

Write-Host ""
Write-Host "  GOTOWE!" -ForegroundColor Green
Write-Host ""
Write-Host "  Adres aplikacji:" -ForegroundColor Yellow
Write-Host "  $url" -ForegroundColor White
Write-Host ""
Write-Host "  Otworz ten adres na iPhone w Safari i dodaj do ekranu poczatkowego."
Write-Host "  Strona moze byc gotowa po 1-2 minutach."
Write-Host ""
Write-Host "  Ustawienia repozytorium:"
Write-Host "  https://github.com/$full"
Write-Host ""

Start-Process $url

Read-Host "Nacisnij Enter, aby zamknac"
