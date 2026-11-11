# Krok 3 (i każde kolejne wdrożenie): obraz → migracje bazy (zadanie) → aplikacja na nowym obrazie.
# Pierwsze uruchomienie po kroku 2:  .\deploy\azure\3-wdrozenie.ps1 -SkipBuild   (obraz zbudował już krok 1)
# Kolejne wdrożenia zmian w kodzie: .\deploy\azure\3-wdrozenie.ps1
param([switch]$SkipBuild)
. "$PSScriptRoot\config.ps1"
# Windows PowerShell 5.1 domyślnie nie używa TLS 1.2, a bez niego nie połączy się z aplikacją przez HTTPS.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

if ($SkipBuild) {
    $ImageRef = Get-AzValue containerapp job show -g $Rg -n $Job --query "properties.template.containers[0].image"
} else {
    $Tag = (Get-Date -Format "yyyyMMdd-HHmm")
    Write-Host "== Budowa obrazu owoce:$Tag i wysłanie do ACR"
    Publish-Image $Tag
    $ImageRef = "${Image}:$Tag"
    Invoke-AzRetry containerapp job update -g $Rg -n $Job --image $ImageRef -o none
}
Write-Host "== Obraz: $ImageRef"

Write-Host "== Migracje bazy i przykładowe zdjęcia (zadanie $Job)"
$Execution = Get-AzValue containerapp job start -g $Rg -n $Job --query name
$Deadline = (Get-Date).AddMinutes(20)
do {
    Start-Sleep -Seconds 15
    $Status = Get-AzValue containerapp job execution show -g $Rg -n $Job --job-execution-name $Execution --query properties.status
    Write-Host "   status: $Status"
} while ($Status -notin @("Succeeded", "Failed", "Stopped", "Degraded") -and (Get-Date) -lt $Deadline)
if ($Status -ne "Succeeded") {
    throw "Zadanie migracji nie powiodło się ($Status). Logi: portal Azure → $Job → Execution history → Logs."
}

Write-Host "== Aplikacja na obrazie $ImageRef (Container Apps podmienia instancje bez przerwy w działaniu)"
Invoke-AzRetry containerapp update -g $Rg -n $App --image $ImageRef -o none

$Fqdn = Get-AzValue containerapp show -g $Rg -n $App --query properties.configuration.ingress.fqdn
Write-Host "== Sprawdzenie https://$Fqdn/healthz/"
$Healthy = $false
for ($i = 0; $i -lt 18 -and -not $Healthy; $i++) {
    try {
        $r = Invoke-RestMethod "https://$Fqdn/healthz/" -TimeoutSec 15
        if ($r.status -eq "ok") { $Healthy = $true; Write-Host "   OK – aplikacja działa i ma połączenie z bazą." }
    } catch { Write-Host "   jeszcze nie gotowa, czekam..." }
    if (-not $Healthy) { Start-Sleep -Seconds 10 }
}
if (-not $Healthy) { throw "Aplikacja nie odpowiada poprawnie na /healthz/. Logi: portal Azure → $App → Log stream." }
Write-Host ""
Write-Host "Aplikacja: https://$Fqdn"