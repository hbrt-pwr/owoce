# Krok 5: wysyłka e-maili (link „Nie pamiętasz hasła?”) przez skrzynkę w home.pl.
# Uruchamia użytkownik – skrypt pyta o hasło do skrzynki i zapisuje je jako sekret Container Apps
# (nie trafia do repozytorium, zmiennych ani historii poleceń).
#   powershell -ExecutionPolicy Bypass -File .\deploy\azure\5-poczta.ps1
# Nazwa serwera SMTP: panel home.pl → Poczta → skrzynka → „Konfiguracja programu pocztowego”
# (postać serwerXXXXXX.home.pl). Port 465 = SSL, 587 = STARTTLS.
param(
    [string]$SmtpHost,
    [int]$Port = 465,
    [string]$User = "kontakt@owocownik.pl",
    [string]$From = "Owocownik <kontakt@owocownik.pl>",
    # Sekret email-host-password dodany już ręcznie w Portalu Azure (Container App owoce → Secrets)
    [switch]$SkipSecret
)
. "$PSScriptRoot\config.ps1"

if (-not $SmtpHost) { $SmtpHost = (Read-Host "Serwer SMTP z panelu home.pl (np. serwer123456.home.pl)").Trim() }
if (-not $SmtpHost) { throw "Nie podano serwera SMTP." }

if (-not $SkipSecret) {
    $secure = Read-Host "Hasło do skrzynki $User" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if (-not $Password) { throw "Nie podano hasła." }
    if ($Password.Contains('"') -or $Password.EndsWith('\')) {
        throw ('Hasło zawiera " albo kończy się na \ – nie da się go bezpiecznie przekazać do az. Dodaj sekret ' +
            'email-host-password ręcznie w Portalu Azure (Container App owoce → Secrets) i uruchom skrypt z -SkipSecret.')
    }

    # Hasło przekazujemy do Pythona z Azure CLI bezpośrednio, z pominięciem az.cmd: cmd.exe psułby
    # znaki specjalne w haśle (%, ^, &, !).
    $azCmd = (Get-Command az -ErrorAction Stop).Source
    $azPython = Join-Path (Split-Path (Split-Path $azCmd)) "python.exe"
    if (-not (Test-Path $azPython)) { throw "Nie znaleziono $azPython (Python z Azure CLI)." }

    Write-Host "== Sekret email-host-password w aplikacji $App"
    & $azPython -IBm azure.cli containerapp secret set -g $Rg -n $App --secrets "email-host-password=$Password" -o none
    $code = $LASTEXITCODE
    $Password = $null
    if ($code -ne 0) { throw "Nie udało się zapisać sekretu (kod $code)." }
}

Write-Host "== Zmienne poczty (nowa rewizja aplikacji)"
Invoke-Az containerapp update -g $Rg -n $App -o none --set-env-vars `
    "EMAIL_HOST=$SmtpHost" "EMAIL_PORT=$Port" "EMAIL_HOST_USER=$User" `
    "EMAIL_HOST_PASSWORD=secretref:email-host-password" "DJANGO_DEFAULT_FROM_EMAIL=$From"

Write-Host ""
Write-Host "Gotowe. Test wysyłki (po wdrożeniu nowego obrazu skryptem 3-wdrozenie.ps1):"
Write-Host "  az containerapp exec -g $Rg -n $App --command `"python manage.py sendtestemail twoj@adres.pl`""
