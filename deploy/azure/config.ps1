# Wspólne ustawienia wdrożenia Owocownik w Azure – wczytywane przez pozostałe skrypty.
# Nazwy ACR, Storage i PostgreSQL muszą być unikalne w całym Azure, stąd przyrostek $Suffix.
$ErrorActionPreference = "Stop"

$Location = "polandcentral"
$Suffix   = "fr7k2"

$Rg      = "rg-owoce"
$Acr     = "acrowoce$Suffix"          # Azure Container Registry – obrazy aplikacji
$Storage = "stowoce$Suffix"           # Storage Account – zdjęcia owoców (kontener media)
$Pg      = "psql-owoce-$Suffix"       # PostgreSQL Flexible Server
$PgDb    = "owoce"
$PgAdmin = "owoceadmin"
$CaEnv   = "cae-owoce"                # środowisko Container Apps (wspólny load balancer + sieć + logi)
$App     = "owoce"                    # Container App – aplikacja Django
$Job     = "owoce-init"               # Container Apps Job – migracje przy wdrożeniu

$Image   = "$Acr.azurecr.io/owoce"

# Skalowanie: zawsze co najmniej 1 instancja, maks. 4; nowa instancja co 30 równoczesnych żądań.
$MinReplicas     = 1
$MaxReplicas     = 4
$HttpConcurrency = 30
$Cpu             = "0.25"
$Memory          = "0.5Gi"

function Invoke-Az {
    # Wywołuje az i przerywa skrypt przy błędzie (az to program zewnętrzny – sam nie rzuca wyjątków).
    & az @args
    if ($LASTEXITCODE -ne 0) { throw "Polecenie az zakończyło się błędem (kod $LASTEXITCODE)." }
}

function Publish-Image([string]$Tag) {
    # Obraz budujemy lokalnie (Docker Desktop) i wysyłamy do ACR – subskrypcja Azure for Students
    # nie pozwala na budowanie w chmurze (ACR Tasks / az acr build).
    $root = (Resolve-Path "$PSScriptRoot\..\..").Path
    Invoke-Az acr login -n $Acr
    & docker build --platform linux/amd64 -t "${Image}:$Tag" -t "${Image}:latest" $root
    if ($LASTEXITCODE -ne 0) { throw "Budowa obrazu nie powiodła się." }
    foreach ($t in $Tag, "latest") {
        & docker push "${Image}:$t"
        if ($LASTEXITCODE -ne 0) { throw "Wysłanie obrazu do ACR nie powiodło się." }
    }
}

function Test-AzExists {
    # Czy zasób istnieje? Np.: Test-AzExists containerapp show -g $Rg -n $App
    # Lokalnie "Continue": PowerShell 5.1 przy "Stop" przerywa skrypt na każdym ostrzeżeniu az wypisanym na stderr.
    $ErrorActionPreference = "Continue"
    & az @args --query id -o tsv 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Grant-Role([string]$Principal, [string]$Role, [string]$Scope) {
    # Uwaga: bez nawiasów w --query (np. "length(@)") – az.cmd na Windows przepuszcza argumenty przez cmd.exe,
    # który nawiasów nie obsługuje i zwraca śmieciowy wynik.
    $ErrorActionPreference = "Continue"
    $ids = & az role assignment list --assignee $Principal --role $Role --scope $Scope --query "[].id" -o tsv 2>$null
    $listed = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = "Stop"
    if ($listed -and ($ids | Where-Object { $_ -like "/subscriptions/*" })) { return }
    # Ponowienia: świeżo utworzona tożsamość bywa przez chwilę niewidoczna dla systemu uprawnień.
    Invoke-AzRetry role assignment create --assignee-object-id $Principal --assignee-principal-type ServicePrincipal `
        --role $Role --scope $Scope -o none
}

function Invoke-AzRetry {
    # Ponawia polecenie – nadanie uprawnień w Azure rozchodzi się do kilku minut, a Azure bywa chwilowo niedostępny.
    for ($i = 1; $i -le 10; $i++) {
        & az @args
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "   próba $i nieudana, ponawiam za 30 s..."
        Start-Sleep -Seconds 30
    }
    throw "Polecenie az nie powiodło się mimo ponowień."
}

function Get-AzValue {
    $out = & az @args -o tsv
    if ($LASTEXITCODE -ne 0) { throw "Polecenie az zakończyło się błędem (kod $LASTEXITCODE)." }
    return ($out | Out-String).Trim()
}
