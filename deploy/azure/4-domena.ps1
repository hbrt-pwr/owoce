# Krok 4 (gdy grupa ma domenę): własna domena + darmowy certyfikat TLS zarządzany przez Azure.
# Certyfikat jest na ingressie Container Apps (load balancer), a nie w kontenerze aplikacji, i Azure sam go odnawia.
#
# Domena główna (np. twojadomena.pl) – rekord A na stały adres IP środowiska Container Apps, certyfikat
# weryfikowany przez HTTP. Opcjonalnie także www.twojadomena.pl (-Www):
#   powershell -ExecutionPolicy Bypass -File .\deploy\azure\4-domena.ps1 -Domain twojadomena.pl -Www
# Subdomena (np. owoce.twojadomena.pl) – rekord CNAME na adres aplikacji w Azure:
#   powershell -ExecutionPolicy Bypass -File .\deploy\azure\4-domena.ps1 -Domain owoce.twojadomena.pl
# Rodzaj domeny jest rozpoznawany po liczbie członów (twojadomena.pl = główna). Dla domen typu firma.com.pl
# dopisz -Apex (to też domena główna), a -Subdomain wymusza tryb subdomeny.
param(
    [Parameter(Mandatory = $true)][string]$Domain,
    [switch]$Www,
    [switch]$Apex,
    [switch]$Subdomain
)
. "$PSScriptRoot\config.ps1"

$Domain = ($Domain.Trim().ToLower() -replace '^https?://', '').TrimEnd('/').TrimEnd('.')
$Labels = $Domain.Split('.')
$IsApex = if ($Apex) { $true } elseif ($Subdomain) { $false } else { $Labels.Count -eq 2 }
if ($Www -and -not $IsApex) { throw "-Www ma sens tylko dla domeny głównej (np. twojadomena.pl)." }
if (-not $IsApex -and $Labels.Count -lt 3) { throw "$Domain to domena główna – uruchom bez -Subdomain." }
# Strefa DNS u rejestratora: dla domeny głównej sama domena, dla subdomeny dwa ostatnie człony.
$Zone = if ($IsApex) { $Domain } else { ($Labels[-2..-1]) -join "." }

$Fqdn = Get-AzValue containerapp show -g $Rg -n $App --query properties.configuration.ingress.fqdn
$VerificationId = Get-AzValue containerapp show -g $Rg -n $App --query properties.customDomainVerificationId
$StaticIp = Get-AzValue containerapp env show -g $Rg -n $CaEnv --query properties.staticIp

# Lista adresów do podpięcia: Kind = "A" (domena główna) albo "CNAME" (subdomena / www)
$Hosts = @()
if ($IsApex) {
    $Hosts += [pscustomobject]@{ Name = $Domain; Kind = "A"; Rel = "@"; Validation = "HTTP" }
    if ($Www) { $Hosts += [pscustomobject]@{ Name = "www.$Domain"; Kind = "CNAME"; Rel = "www"; Validation = "CNAME" } }
} else {
    # Nazwa względna w panelu DNS (zakładamy strefę = dwa ostatnie człony, np. twojadomena.pl)
    $rel = ($Labels[0..($Labels.Count - 3)]) -join '.'
    $Hosts += [pscustomobject]@{ Name = $Domain; Kind = "CNAME"; Rel = $rel; Validation = "CNAME" }
}

Write-Host ""
Write-Host ("Tryb: " + $(if ($IsApex) { "domena główna" } else { "subdomena" }) + " – $Domain")
Write-Host ""
Write-Host "Dodaj w panelu DNS rejestratora (np. home.pl → domena → strefa DNS) rekordy:"
Write-Host ""
Write-Host ("  {0,-6} {1,-22} {2}" -f "TYP", "NAZWA", "WARTOŚĆ")
foreach ($h in $Hosts) {
    $txtName = if ($h.Rel -eq "@") { "asuid" } else { "asuid.$($h.Rel)" }
    if ($h.Kind -eq "A") { Write-Host ("  {0,-6} {1,-22} {2}" -f "A", "@ (sama domena)", $StaticIp) }
    else { Write-Host ("  {0,-6} {1,-22} {2}" -f "CNAME", $h.Rel, $Fqdn) }
    Write-Host ("  {0,-6} {1,-22} {2}" -f "TXT", $txtName, $VerificationId)
}
Write-Host ""
Write-Host "Ważne:"
if ($IsApex) {
    Write-Host " - Usuń inne rekordy A i AAAA dla samej domeny (@), np. domyślny adres strony parkingowej rejestratora."
    Write-Host "   Rekordów MX i TXT poczty nie ruszaj."
}
if ($Www) { Write-Host " - Usuń istniejące rekordy A / AAAA / CNAME dla www, jeśli są." }
Write-Host " - W panelu zwykle wpisuje się tylko nazwę względną (kolumna NAZWA), bez '.$Zone'."
Write-Host ""

function Test-HostDns($h) {
    # Sprawdzenie w publicznym DNS (1.1.1.1), czy rekordy już są widoczne.
    $ok = $true
    try {
        $txt = Resolve-DnsName -Name "asuid.$($h.Name)" -Type TXT -Server 1.1.1.1 -DnsOnly -ErrorAction Stop |
            Where-Object { $_.Type -eq "TXT" } | ForEach-Object { $_.Strings }
        if ($txt -notcontains $VerificationId) { Write-Host "   $($h.Name): rekord TXT asuid jeszcze niewidoczny lub inny"; $ok = $false }
    } catch { Write-Host "   $($h.Name): rekord TXT asuid jeszcze niewidoczny"; $ok = $false }
    try {
        if ($h.Kind -eq "A") {
            $ips = Resolve-DnsName -Name $h.Name -Type A -Server 1.1.1.1 -DnsOnly -ErrorAction Stop |
                Where-Object { $_.Type -eq "A" } | ForEach-Object { $_.IPAddress }
            if (@($ips).Count -ne 1 -or $ips -ne $StaticIp) {
                Write-Host "   $($h.Name): rekordy A = $($ips -join ', ') (oczekiwany tylko $StaticIp)"; $ok = $false
            }
        } else {
            $cname = Resolve-DnsName -Name $h.Name -Type CNAME -Server 1.1.1.1 -DnsOnly -ErrorAction Stop |
                Where-Object { $_.Type -eq "CNAME" } | ForEach-Object { $_.NameHost.TrimEnd('.') }
            if ($cname -ne $Fqdn) { Write-Host "   $($h.Name): CNAME = '$cname' (oczekiwany $Fqdn)"; $ok = $false }
        }
    } catch { Write-Host "   $($h.Name): rekord $($h.Kind) jeszcze niewidoczny"; $ok = $false }
    return $ok
}

while ($true) {
    $answer = Read-Host "Naciśnij Enter, gdy rekordy będą dodane (wpisz 'pomin', żeby nie sprawdzać DNS)"
    if ($answer -eq "pomin") { break }
    $ready = $true
    foreach ($h in $Hosts) { if (-not (Test-HostDns $h)) { $ready = $false } }
    if ($ready) { Write-Host "   DNS gotowy."; break }
    Write-Host "   Propagacja DNS trwa zwykle kilka–kilkanaście minut (czasem dłużej) – spróbuj za chwilę."
}

$ErrorActionPreference = "Continue"
$Existing = & az containerapp hostname list -g $Rg -n $App --query "[].name" -o tsv 2>$null
$ErrorActionPreference = "Stop"

foreach ($h in $Hosts) {
    Write-Host "== $($h.Name): dodanie domeny i darmowy certyfikat (weryfikacja $($h.Validation), może potrwać do ~20 minut)"
    if (@($Existing) -notcontains $h.Name) {
        Invoke-AzRetry containerapp hostname add -g $Rg -n $App --hostname $h.Name -o none
    }
    Invoke-AzRetry containerapp hostname bind -g $Rg -n $App --hostname $h.Name --environment $CaEnv `
        --validation-method $h.Validation -o none
}

Write-Host "== Django akceptuje nowe adresy"
$AllHosts = @($Hosts | ForEach-Object { $_.Name }) + $Fqdn
Invoke-AzRetry containerapp update -g $Rg -n $App `
    --set-env-vars "DJANGO_ALLOWED_HOSTS=$($AllHosts -join ',')" `
    "DJANGO_CSRF_TRUSTED_ORIGINS=$(($AllHosts | ForEach-Object { "https://$_" }) -join ',')" -o none

Write-Host ""
foreach ($h in $Hosts) { Write-Host "Gotowe: https://$($h.Name)" }
Write-Host "Jeśli aplikacja jest zapauzowana, uruchom najpierw .\deploy\azure\wznow.ps1 – inaczej strona pokaże błąd bazy."
