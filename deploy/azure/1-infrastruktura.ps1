# Krok 1: infrastruktura bez sekretów – grupa zasobów, rejestr obrazów, zbudowany obraz,
# Storage na zdjęcia, środowisko Container Apps, aplikacja (ze skalowaniem) i zadanie migracji.
# Uruchomienie (z katalogu głównego repozytorium):  .\deploy\azure\1-infrastruktura.ps1
. "$PSScriptRoot\config.ps1"

Write-Host "== Rejestracja dostawców zasobów (jednorazowo na subskrypcję)"
foreach ($ns in "Microsoft.App", "Microsoft.OperationalInsights", "Microsoft.ContainerRegistry",
                "Microsoft.DBforPostgreSQL", "Microsoft.Storage") {
    Invoke-Az provider register --namespace $ns --wait -o none
}
Invoke-Az extension add --name containerapp --upgrade --only-show-errors -o none

Write-Host "== Grupa zasobów $Rg ($Location)"
Invoke-Az group create -n $Rg -l $Location -o none

Write-Host "== Container Registry $Acr + budowa obrazu (lokalnie, Docker Desktop) i wysłanie do rejestru"
Invoke-Az acr create -g $Rg -n $Acr --sku Basic --admin-enabled false -o none
$Tag = (Get-Date -Format "yyyyMMdd-HHmm")
Publish-Image $Tag
$ImageRef = "${Image}:$Tag"

Write-Host "== Storage $Storage – kontener 'media' z publicznym odczytem plików (bez listowania)"
Invoke-Az storage account create -g $Rg -n $Storage -l $Location --sku Standard_LRS --kind StorageV2 `
    --min-tls-version TLS1_2 --allow-blob-public-access true -o none
Invoke-Az storage container-rm create --storage-account $Storage -g $Rg -n media --public-access blob -o none
$StorageId = Get-AzValue storage account show -g $Rg -n $Storage --query id

Write-Host "== Środowisko Container Apps $CaEnv (tworzy też Log Analytics na logi)"
# Tryb WorkloadProfiles (profil Consumption – płatność za użycie). Domyślny tryb "Express" nie pozwala
# pobierać obrazu z ACR tożsamością zarządzaną.
if (-not (Test-AzExists containerapp env show -g $Rg -n $CaEnv)) {
    Invoke-Az containerapp env create -g $Rg -n $CaEnv -l $Location --environment-mode WorkloadProfiles -o none
}

$CommonEnv = @("DJANGO_DEBUG=0", "AZURE_ACCOUNT_NAME=$Storage", "AZURE_CONTAINER=media")
$AcrId = Get-AzValue acr show -n $Acr --query id

# Aplikację i zadanie tworzymy z publicznym obrazem testowym i tożsamością zarządzaną, a rejestr i właściwy obraz
# podpinamy osobno (z ponowieniami). Wbudowany w az dwuetapowy mechanizm (--registry-identity przy tworzeniu)
# bywał przerywany chwilowym błędem Azure. Skrypt można też bezpiecznie uruchomić ponownie.
$Placeholder = "mcr.microsoft.com/k8se/quickstart:latest"

Write-Host "== Aplikacja ${App}: ingress HTTPS (TLS na load balancerze), autoskalowanie $MinReplicas-$MaxReplicas"
if (-not (Test-AzExists containerapp show -g $Rg -n $App)) {
    Invoke-AzRetry containerapp create -g $Rg -n $App --environment $CaEnv `
        --image $Placeholder --system-assigned `
        --ingress external --target-port 8000 --transport auto `
        --cpu $Cpu --memory $Memory `
        --min-replicas $MinReplicas --max-replicas $MaxReplicas `
        --scale-rule-name http-rule --scale-rule-type http --scale-rule-http-concurrency $HttpConcurrency `
        --env-vars @CommonEnv "GUNICORN_WORKERS=2" "DJANGO_ALLOWED_HOSTS=localhost" -o none
}
Grant-Role (Get-AzValue containerapp show -g $Rg -n $App --query identity.principalId) "AcrPull" $AcrId
Invoke-AzRetry containerapp registry set -g $Rg -n $App --server "$Acr.azurecr.io" --identity system -o none
$Fqdn = Get-AzValue containerapp show -g $Rg -n $App --query properties.configuration.ingress.fqdn
# Obraz aplikacji podmienia dopiero krok 3 (po migracjach) – bez bazy i sekretów (krok 2) aplikacja celowo nie startuje.
Invoke-AzRetry containerapp update -g $Rg -n $App `
    --set-env-vars "DJANGO_ALLOWED_HOSTS=$Fqdn" "DJANGO_CSRF_TRUSTED_ORIGINS=https://$Fqdn" -o none

Write-Host "== Zadanie ${Job}: migracje + przykładowe zdjęcia (uruchamiane ręcznie przy wdrożeniu)"
if (-not (Test-AzExists containerapp job show -g $Rg -n $Job)) {
    Invoke-AzRetry containerapp job create -g $Rg -n $Job --environment $CaEnv `
        --trigger-type Manual --replica-timeout 900 --replica-retry-limit 0 --parallelism 1 --replica-completion-count 1 `
        --image $Placeholder --mi-system-assigned `
        --cpu $Cpu --memory $Memory `
        --command "python" --args "manage.py" "init_db" `
        --env-vars @CommonEnv -o none
}
Grant-Role (Get-AzValue containerapp job show -g $Rg -n $Job --query identity.principalId) "AcrPull" $AcrId
Invoke-AzRetry containerapp job registry set -g $Rg -n $Job --server "$Acr.azurecr.io" --identity system -o none
Invoke-AzRetry containerapp job update -g $Rg -n $Job --image $ImageRef -o none

Write-Host "== Uprawnienia: aplikacja i zadanie zapisują zdjęcia w Storage swoją tożsamością (bez klucza)"
Grant-Role (Get-AzValue containerapp show -g $Rg -n $App --query identity.principalId) "Storage Blob Data Contributor" $StorageId
Grant-Role (Get-AzValue containerapp job show -g $Rg -n $Job --query identity.principalId) "Storage Blob Data Contributor" $StorageId

Write-Host ""
Write-Host "Gotowe. Adres aplikacji (po kroku 3): https://$Fqdn"
Write-Host "Następny krok – baza i sekrety: .\deploy\azure\2-baza-i-sekrety.ps1"
