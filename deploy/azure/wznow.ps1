# Wznowienie po pauzie: start bazy, aplikacja wraca do stałej minimalnej liczby instancji, sprawdzenie /healthz/.
# Uruchomienie:  powershell -ExecutionPolicy Bypass -File .\deploy\azure\wznow.ps1
. "$PSScriptRoot\config.ps1"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function Get-PgServerName {
    # Nazwa serwera bazy utworzonego w kroku 2 (z przyrostkiem regionu, np. psql-owoce-fr7k2-chn).
    $names = Get-AzValue postgres flexible-server list -g $Rg --query "[].name"
    $name = $names -split "\s+" | Where-Object { $_ -like "$Pg-*" } | Select-Object -First 1
    if (-not $name) { throw "Nie znaleziono serwera bazy $Pg-* w grupie $Rg." }
    return $name
}
$Server = Get-PgServerName
$State = Get-AzValue postgres flexible-server show -g $Rg -n $Server --query state
if ($State -ne "Ready") {
    Write-Host "== Start bazy $Server (kilka minut)"
    Invoke-Az postgres flexible-server start -g $Rg -n $Server -o none
}

Write-Host "== Aplikacja ${App}: minimum $MinReplicas instancji"
Invoke-AzRetry containerapp update -g $Rg -n $App --min-replicas $MinReplicas -o none

$Fqdn = Get-AzValue containerapp show -g $Rg -n $App --query properties.configuration.ingress.fqdn
$Healthy = $false
for ($i = 0; $i -lt 18 -and -not $Healthy; $i++) {
    try { if ((Invoke-RestMethod "https://$Fqdn/healthz/" -TimeoutSec 15).status -eq "ok") { $Healthy = $true } } catch { }
    if (-not $Healthy) { Write-Host "   czekam na aplikację..."; Start-Sleep -Seconds 10 }
}
if (-not $Healthy) { throw "Aplikacja nie odpowiada na /healthz/. Logi: portal Azure → $App → Log stream." }
Write-Host ""
Write-Host "Działa: https://$Fqdn"