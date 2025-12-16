# Script PowerShell d'arrêt pour pipeline IoT streaming Kidjamo
# Usage: .\stop_pipeline.ps1

param(
    [switch]$CleanData = $false
)

Write-Host "🛑 Stopping Kidjamo IoT Streaming Pipeline..." -ForegroundColor Red

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Info($message) {
    Write-Host "ℹ️  $message" -ForegroundColor Blue
}

function Write-Success($message) {
    Write-Host "✅ $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "⚠️  $message" -ForegroundColor Yellow
}

# Arrêt des processus Python
function Stop-PythonProcesses {
    Write-Info "Stopping Python processes..."

    # Arrêt des processus sur les ports spécifiques
    $processes = @(
        @{Name="API"; Port=8001},
        @{Name="Simulator"; Pattern="medical_iot_simulator"},
        @{Name="Streaming"; Pattern="iot_streaming_processor"}
    )

    foreach ($proc in $processes) {
        if ($proc.Port) {
            $netstat = netstat -ano | Select-String ":$($proc.Port)"
            if ($netstat) {
                $pid = ($netstat -split '\s+')[-1]
                try {
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    Write-Success "$($proc.Name) stopped (PID: $pid)"
                }
                catch {
                    Write-Warning "Could not stop $($proc.Name)"
                }
            }
        }

        if ($proc.Pattern) {
            Get-Process | Where-Object { $_.ProcessName -like "*python*" } | ForEach-Object {
                $cmdLine = (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
                if ($cmdLine -and $cmdLine.Contains($proc.Pattern)) {
                    try {
                        Stop-Process -Id $_.Id -Force
                        Write-Success "$($proc.Name) stopped (PID: $($_.Id))"
                    }
                    catch {
                        Write-Warning "Could not stop $($proc.Name)"
                    }
                }
            }
        }
    }
}

# Arrêt de Kafka
function Stop-Kafka {
    Write-Info "Stopping Kafka infrastructure..."

    try {
        Set-Location kafka
        docker-compose down
        Write-Success "Kafka stopped"
        Set-Location ..
    }
    catch {
        Write-Warning "Error stopping Kafka: $_"
        Set-Location ..
    }
}

# Nettoyage des données
function Clear-Data {
    if ($CleanData) {
        Write-Warning "Cleaning data lake..."

        $paths = @(
            "data_lake\raw\*",
            "data_lake\bronze\*",
            "data_lake\silver\*",
            "checkpoints\*"
        )

        foreach ($path in $paths) {
            Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
        }

        Write-Success "Data cleaned"
    }
}

# Fonction principale
function Main {
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "🛑 Kidjamo IoT Pipeline Shutdown" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan

    Stop-PythonProcesses
    Stop-Kafka
    Clear-Data

    Write-Success "Pipeline stopped successfully!"
    Write-Host ""
    Write-Host "💡 Options:" -ForegroundColor Yellow
    Write-Host '  * .\stop_pipeline.ps1 -CleanData (remove all data)'
    Write-Host '  * .\start_pipeline.ps1 (restart pipeline)'
}

Main
