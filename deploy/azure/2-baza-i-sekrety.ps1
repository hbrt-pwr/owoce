# Krok 2: baza PostgreSQL i sekrety aplikacji.
# Hasło administratora bazy i DJANGO_SECRET_KEY są losowane tutaj, od razu trafiają do Azure
# (sekrety Container Apps) i nigdzie się nie wyświetlają ani nie zapisują na dysku.
# Uruchomienie (z katalogu głównego repozytorium):  .\deploy\azure\2-baza-i-sekrety.ps1
. "$PSScriptRoot\config.ps1"

function New-RandomString([int]$Length) {
    # Litery i cyfry – bez znaków specjalnych, żeby hasło nie psuło adresu DATABASE_URL.
    $chars = [char[]]"abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

$PgPassword = New-RandomString 32
$SecretKey  = New-RandomString 64

# Regiony dozwolone dla subskrypcji Azure for Students. Studencka oferta w części regionów nie pozwala tworzyć
# PostgreSQL (np. "location is restricted", "SkuNotAvailable") – regiony zablokowane według Azure pomijamy od razu,
# a przy odmowie próbujemy kolejnego. Aplikacja zostaje w $Location; baza w innym regionie dodaje kilkanaście ms.
$PgCandidates = [ordered]@{
    "switzerlandnorth" = "chn"; "norwayeast" = "noe"; "spaincentral" = "spc"; "polandcentral" = "plc"; "germanywestcentral" = "gwc"
}
# Najpierw najtańszy B1ms; jeśli nigdzie go nie ma – B2s (2 vCPU, ok. 2× droższy).
$PgSkus = [ordered]@{ "Standard_B1ms" = ""; "Standard_B2s" = "2" }
$Unavailable = "SkuNotAvailable|NotAvailableForSubscription|LocationIsOfferRestricted|OfferRestricted|location is restricted|Provisioning is restricted|QuotaExceeded|RequestDisallowedByPolicy|ServerCreationNotAllowed|RegionDoesNotAllowProvisioning"

function Get-PgRegionBlock([string]$Region) {
    # Powód blokady zgłaszany przez Azure dla regionu (pusty = brak blokady) – bez tworzenia czegokolwiek.
    $ErrorActionPreference = "Continue"
    $caps = & az postgres flexible-server list-skus -l $Region -o json 2>$null | ConvertFrom-Json | Select-Object -First 1
    if (-not $caps) { return "brak informacji o regionie" }
    if ($caps.reason) { return $caps.reason }
    if (-not ($caps.supportedServerEditions | Where-Object { $_.name -eq "Burstable" })) { return "brak serwerów Burstable" }
    return ""
}

# Ponowne uruchomienie: działający serwer z poprzedniej próby – używamy go i ustawiamy mu nowe hasło.
$ErrorActionPreference = "Continue"
# (bez nawiasów i && w --query – az.cmd przepuszcza argumenty przez cmd.exe; filtrujemy w PowerShellu)
$Existing = & az postgres flexible-server list -g $Rg --query "[].[name,state]" -o tsv 2>$null
$ErrorActionPreference = "Stop"
$PgServer = $Existing | ForEach-Object { $n, $s = "$_" -split "`t"; if ($n -like "$Pg-*" -and $s -eq "Ready") { $n } } |
    Select-Object -First 1

if ($PgServer) {
    Write-Host "== Serwer $PgServer już istnieje – ustawiam nowe hasło administratora"
    Invoke-Az postgres flexible-server update -g $Rg -n $PgServer --admin-password $PgPassword -o none
} else {
    $Blocked = @{}
    foreach ($PgLocation in $PgCandidates.Keys) {
        $why = Get-PgRegionBlock $PgLocation
        if ($why) { $Blocked[$PgLocation] = $true; Write-Host "   pomijam $PgLocation – Azure zgłasza blokadę: $why" }
    }
    foreach ($Sku in $PgSkus.Keys) {
        foreach ($PgLocation in $PgCandidates.Keys) {
            if ($Blocked[$PgLocation]) { continue }
            $Name = "$Pg-$($PgCandidates[$PgLocation])$($PgSkus[$Sku])"
            Write-Host "== PostgreSQL Flexible Server $Name w $PgLocation ($Sku, 32 GB z auto-powiększaniem, PostgreSQL 16)"
            Write-Host "   (to trwa zwykle 5–10 minut)"
            $ErrorActionPreference = "Continue"
            $out = & az postgres flexible-server create -g $Rg -n $Name -l $PgLocation `
                --tier Burstable --sku-name $Sku --storage-size 32 --storage-auto-grow Enabled --version 16 `
                --admin-user $PgAdmin --admin-password $PgPassword `
                --public-access 0.0.0.0 --yes -o none 2>&1 | ForEach-Object { "$_" }
            $ok = ($LASTEXITCODE -eq 0)
            $ErrorActionPreference = "Stop"
            if ($ok) { $PgServer = $Name; break }
            $text = $out -join "`n"
            if ($text -match $Unavailable) {
                Write-Host "   $PgLocation odmówił ($($Matches[0])) – próbuję dalej"
                continue
            }
            Write-Host $text
            throw "Tworzenie bazy nie powiodło się (powyżej komunikat Azure)."
        }
        if ($PgServer) { break }
    }
    if (-not $PgServer) { throw "Żaden z dozwolonych regionów nie pozwolił utworzyć serwera PostgreSQL (B1ms ani B2s) dla tej subskrypcji." }
}$Pg = $PgServer
$Dbs = Get-AzValue postgres flexible-server db list -g $Rg -s $Pg --query "[].name"
if (-not (($Dbs -split "\s+") -contains $PgDb)) {
    Invoke-Az postgres flexible-server db create -g $Rg -s $Pg -n $PgDb -o none
}
$DatabaseUrl = "postgres://${PgAdmin}:$PgPassword@$Pg.postgres.database.azure.com:5432/${PgDb}?sslmode=require"

Write-Host "== Sekrety aplikacji i zadania migracji (Container Apps secrets)"
$Secrets = @("django-secret-key=$SecretKey", "database-url=$DatabaseUrl")
$SecretEnv = @("DJANGO_SECRET_KEY=secretref:django-secret-key", "DATABASE_URL=secretref:database-url")

Invoke-Az containerapp secret set -g $Rg -n $App --secrets @Secrets -o none
Invoke-Az containerapp job secret set -g $Rg -n $Job --secrets @Secrets -o none
Invoke-Az containerapp job update -g $Rg -n $Job --set-env-vars @SecretEnv -o none
Invoke-Az containerapp update -g $Rg -n $App --set-env-vars @SecretEnv -o none

Remove-Variable PgPassword, SecretKey, DatabaseUrl, Secrets

Write-Host ""
Write-Host "Gotowe. Baza: $Pg.postgres.database.azure.com (dostęp tylko z usług Azure, połączenia po TLS)."
Write-Host "Następny krok: .\deploy\azure\3-wdrozenie.ps1 (migracje bazy i sprawdzenie aplikacji)."
