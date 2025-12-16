# Script PowerShell simplifié pour démarrer la pipeline IoT Kidjamo
param(
    [switch]$WithSimulator = $false
)

Write-Host "Starting Kidjamo IoT Pipeline..." -ForegroundColor Green

# Aller dans le bon répertoire
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Créer les dossiers nécessaires
$folders = @("logs", "data_lake\raw", "data_lake\bronze", "data_lake\silver", "data_lake\gold")
foreach ($folder in $folders) {
    if (!(Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
    }
}

Write-Host "Setting up Kafka..." -ForegroundColor Yellow
Set-Location "kafka"
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to start Kafka" -ForegroundColor Red
    exit 1
}
Write-Host "Waiting for Kafka to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 20
Set-Location ".."

Write-Host "Starting IoT API..." -ForegroundColor Yellow
$apiJob = Start-Job -ScriptBlock {
    Set-Location $args[0]
    & ".\venv\Scripts\python.exe" "api\iot_ingestion_api.py"
} -ArgumentList (Get-Location)

Write-Host "Starting Stream Processor..." -ForegroundColor Yellow
$streamJob = Start-Job -ScriptBlock {
    Set-Location $args[0]
    & ".\venv\Scripts\python.exe" "streaming\stream_processor.py"
} -ArgumentList (Get-Location)

if ($WithSimulator) {
    Write-Host "Starting IoT Simulator..." -ForegroundColor Yellow
    $simJob = Start-Job -ScriptBlock {
        Set-Location $args[0]
        & ".\venv\Scripts\python.exe" "simulator\iot_simulator.py"
    } -ArgumentList (Get-Location)
}

Write-Host ""
Write-Host "Pipeline started successfully!" -ForegroundColor Green
Write-Host "Access points:" -ForegroundColor Cyan
Write-Host "- Kafka UI: http://localhost:8090" -ForegroundColor White
Write-Host "- IoT API: http://localhost:5000" -ForegroundColor White
Write-Host "- Health Check: http://localhost:5000/health" -ForegroundColor White
Write-Host ""
Write-Host "To stop: .\stop_pipeline.ps1" -ForegroundColor Red
Write-Host ""

# Attendre un peu pour voir les erreurs de démarrage
Start-Sleep -Seconds 5

# Vérifier l'état des jobs
Write-Host "Job Status:" -ForegroundColor Yellow
Get-Job | Select-Object Name, State

if ($WithSimulator) {
    Write-Host "Simulator is running. Data will be generated automatically." -ForegroundColor Green
}
