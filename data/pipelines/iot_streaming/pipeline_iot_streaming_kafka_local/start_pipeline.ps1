# Script PowerShell de démarrage pour pipeline IoT streaming Kidjamo
# Usage: .\start_pipeline.ps1

param(
    [switch]$WithSimulator,
    [switch]$CleanStart
)

Write-Host "🚀 Starting Kidjamo IoT Streaming Pipeline..." -ForegroundColor Green

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Fonctions utilitaires
function WriteInfo {
    param([string]$message)
    Write-Host "[INFO] $message" -ForegroundColor Blue
}

function WriteSuccess {
    param([string]$message)
    Write-Host "✅ $message" -ForegroundColor Green
}

function WriteWarning {
    param([string]$message)
    Write-Host "⚠️  $message" -ForegroundColor Yellow
}

function WriteError {
    param([string]$message)
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

# Backward-compatibility wrappers for original function names
function Write-Info {
    param([string]$message)
    WriteInfo $message
}

function Write-Success {
    param([string]$message)
    WriteSuccess $message
}

function Write-Warning {
    param([string]$message)
    WriteWarning $message
}

function Write-Error {
    param([string]$message)
    WriteError $message
}

# Vérification des prérequis
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."

    # Docker
    if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is required but not installed"
        exit 1
    }

    # Docker Compose
    if (!(Get-Command docker-compose -ErrorAction SilentlyContinue)) {
        Write-Error "Docker Compose is required but not installed"
        exit 1
    }

    # Python
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "Python is required but not installed"
        exit 1
    }

    # Java (pour Spark si nécessaire)
    try {
        $javaOutput = & java -version 2>&1
        $javaVersionText = ($javaOutput | Select-Object -First 1)
        # formats possibles: 'java version "17.0.8"' ou 'openjdk version "11.0.20"'
        $javaMajor = -1
        if ($javaVersionText -match '"(\d+)\.(\d+)') {
            $javaMajor = [int]$Matches[1]
        }

        if ($javaMajor -eq -1) {
            Write-Warning "Impossible de déterminer la version de Java depuis: $javaVersionText"
        }
    }
    catch {
        Write-Warning "Java non détecté ou erreur lors de la vérification"
    }

    Write-Success "Prerequisites check completed"
}

# Démarrage de Kafka
function Start-Kafka {
    Write-Info "Starting Kafka cluster..."

    Set-Location "kafka"

    if ($CleanStart) {
        Write-Info "Clean start requested - removing volumes..."
        docker-compose down -v
    }

    docker-compose up -d

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start Kafka"
        exit 1
    }

    Write-Info "Waiting for Kafka to be ready..."
    Start-Sleep -Seconds 30

    Set-Location ".."
    Write-Success "Kafka cluster started successfully"
}

# Démarrage de l'API IoT
function Start-IoTAPI {
    Write-Info "Starting IoT Ingestion API..."

    $apiProcess = Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "api\iot_ingestion_api.py" -PassThru -WindowStyle Hidden

    if ($apiProcess) {
        Write-Success "IoT API started (PID: $($apiProcess.Id))"
        "API_PID=$($apiProcess.Id)" | Out-File -FilePath ".\logs\processes.txt" -Append
    } else {
        Write-Error "Failed to start IoT API"
        exit 1
    }
}

# Démarrage du processeur de streaming
function Start-StreamingProcessor {
    Write-Info "Starting Streaming Processor..."

    $streamProcess = Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "streaming\stream_processor.py" -PassThru -WindowStyle Hidden

    if ($streamProcess) {
        Write-Success "Streaming Processor started (PID: $($streamProcess.Id))"
        "STREAM_PID=$($streamProcess.Id)" | Out-File -FilePath ".\logs\processes.txt" -Append
    } else {
        Write-Error "Failed to start Streaming Processor"
        exit 1
    }
}

# Démarrage du simulateur (optionnel)
function Start-Simulator {
    if ($WithSimulator) {
        Write-Info "Starting IoT Simulator..."

        $simProcess = Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "simulator\iot_simulator.py" -PassThru -WindowStyle Hidden

        if ($simProcess) {
            Write-Success "IoT Simulator started (PID: $($simProcess.Id))"
            "SIM_PID=$($simProcess.Id)" | Out-File -FilePath ".\logs\processes.txt" -Append
        } else {
            Write-Error "Failed to start IoT Simulator"
            exit 1
        }
    }
}

# Configuration des dossiers de logs
function Setup-Logging {
    Write-Info "Setting up logging directories..."

    $logDirs = @("logs", "data_lake\raw", "data_lake\bronze", "data_lake\silver", "data_lake\gold", "checkpoints")

    foreach ($dir in $logDirs) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    # Nettoyer le fichier des processus
    if (Test-Path ".\logs\processes.txt") {
        Remove-Item ".\logs\processes.txt"
    }

    Write-Success "Logging setup completed"
}

# Fonction principale
function Main {
    try {
        Write-Host "🏥 Kidjamo IoT Streaming Pipeline Launcher" -ForegroundColor Cyan
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host ""

        Test-Prerequisites
        Setup-Logging
        Start-Kafka
        Start-IoTAPI
        Start-StreamingProcessor
        Start-Simulator

        Write-Host ""
        Write-Host "🎉 Pipeline started successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📊 Access points:" -ForegroundColor Yellow
        Write-Host "  • Kafka UI: http://localhost:8090"
        Write-Host "  • IoT API: http://localhost:5000"
        Write-Host "  • API Health: http://localhost:5000/health"
        Write-Host "  • API Metrics: http://localhost:5000/metrics"
        Write-Host ""
        Write-Host "📁 Data locations:" -ForegroundColor Yellow
        Write-Host "  • Raw data: .\data_lake\raw\"
        Write-Host "  • Bronze data: .\data_lake\bronze\"
        Write-Host "  • Logs: .\logs\"
        Write-Host ""
        Write-Host "🛑 To stop: .\stop_pipeline.ps1" -ForegroundColor Red
        Write-Host ""

        if ($WithSimulator) {
            Write-Host "🔄 Simulator is running. Check logs\simulator.log for activity." -ForegroundColor Green
        }
    }
    catch {
        Write-Error "Pipeline startup failed: $($_.Exception.Message)"
        exit 1
    }
}

# Exécution
Main
