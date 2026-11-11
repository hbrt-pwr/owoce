# Pauza: aplikacja schodzi do 0 instancji (bez ruchu nic nie kosztuje), serwer bazy zostaje zatrzymany.
# Dane zostają. Płacisz tylko za dysk bazy, rejestr obrazów i Storage (razem ok. 5–10 USD/mies.).
# UWAGA: Azure sam włącza zatrzymaną bazę po 7 dniach – przy dłuższej pauzie uruchom ten skrypt ponownie.
# Uruchomienie:  powershell -ExecutionPolicy Bypass -File .\deploy\azure\pauza.ps1
. "$PSScriptRoot\config.ps1"
function Get-PgServerName {
    # Nazwa serwera bazy utworzonego w kroku 2 (z przyrostkiem regionu, np. psql-owoce-fr7k2-chn).
    $names = Get-AzValue postgres flexible-server list -g $Rg --query "[].name"
    $name = $names -split "\s+" | Where-Object { $_ -like "$Pg-*" } | Select-Object -First 1
    if (-not $name) { throw "Nie znaleziono serwera bazy $Pg-* w grupie $Rg." }
    return $name
}
Write-Host "== Aplikacja ${App}: minimum 0 instancji"
Invoke-AzRetry containerapp update -g $Rg -n $App --min-replicas 0 -o none

$Server = Get-PgServerName
$State = Get-AzValue postgres flexible-server show -g $Rg -n $Server --query state
if ($State -eq "Ready") {
    Write-Host "== Zatrzymanie bazy $Server (kilka minut)"
    Invoke-Az postgres flexible-server stop -g $Rg -n $Server -o none
} else {
    Write-Host "== Baza $Server ma stan '$State' – nie zatrzymuję"
}
Write-Host ""
Write-Host "Pauza włączona. Wznowienie: powershell -ExecutionPolicy Bypass -File .\deploy\azure\wznow.ps1"