@echo off
REM Script de démarrage Windows pour simulation massive IoT KIDJAMO
REM Usage: start_massive_simulation.bat [options]

echo ========================================
echo KIDJAMO IoT - Simulation Massive 50+ Patients
echo ========================================

REM Vérification Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python non trouvé. Installez Python 3.8+
    pause
    exit /b 1
)

REM Activation environnement virtuel si présent
if exist venv\Scripts\activate.bat (
    echo Activation environnement virtuel...
    call venv\Scripts\activate.bat
)

REM Configuration par défaut
set PATIENTS=50
set DURATION=24
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=kidjamo
set DB_USER=postgres
set DB_PASSWORD=password

REM Parse arguments simples
if "%1"=="--help" goto :help
if "%1"=="-h" goto :help
if "%1"=="--quick-test" (
    set PATIENTS=5
    set DURATION=0.5
    echo Mode test rapide: 5 patients, 30 minutes
)

REM Vérification dépendances
echo Vérification dépendances Python...
pip install -q streamlit plotly pandas psycopg2-binary twilio kafka-python requests

REM Démarrage simulation
echo.
echo Démarrage simulation avec:
echo   - Patients: %PATIENTS%
echo   - Durée: %DURATION%h
echo   - Base: %DB_HOST%:%DB_PORT%/%DB_NAME%
echo.
echo Dashboard sera disponible sur: http://localhost:8501
echo SMS envoyés vers: +237695607089
echo Emails envoyés vers: christianouragan@gmail.com
echo.
echo Appuyez sur Ctrl+C pour arrêter la simulation
echo.

python massive_simulation_integration.py ^
    --patients %PATIENTS% ^
    --duration %DURATION% ^
    --db-host %DB_HOST% ^
    --db-port %DB_PORT% ^
    --db-name %DB_NAME% ^
    --db-user %DB_USER% ^
    --db-password %DB_PASSWORD% ^
    --test-alerts

goto :end

:help
echo.
echo Usage: start_massive_simulation.bat [options]
echo.
echo Options:
echo   --help, -h        Affiche cette aide
echo   --quick-test      Test rapide (5 patients, 30min)
echo.
echo Configuration par défaut:
echo   - 50 patients
echo   - 24h continues
echo   - PostgreSQL localhost:5432/kidjamo
echo   - Dashboard Streamlit sur port 8501
echo   - Notifications SMS/Email activées
echo.
echo Pour personnaliser, éditez config/massive_simulation_config.json
echo.

:end
pause
