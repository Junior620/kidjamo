#!/bin/bash
# Script de démarrage Linux/MacOS pour simulation massive IoT KIDJAMO
# Usage: ./start_massive_simulation.sh [options]

echo "========================================"
echo "KIDJAMO IoT - Simulation Massive 50+ Patients"
echo "========================================"

# Vérification Python
if ! command -v python3 &> /dev/null; then
    echo "ERREUR: Python 3 non trouvé. Installez Python 3.8+"
    exit 1
fi

# Activation environnement virtuel si présent
if [ -f "venv/bin/activate" ]; then
    echo "Activation environnement virtuel..."
    source venv/bin/activate
fi

# Configuration par défaut
PATIENTS=50
DURATION=24
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kidjamo
DB_USER=postgres
DB_PASSWORD=password

# Parse arguments
case $1 in
    --help|-h)
        echo ""
        echo "Usage: ./start_massive_simulation.sh [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h        Affiche cette aide"
        echo "  --quick-test      Test rapide (5 patients, 30min)"
        echo ""
        echo "Configuration par défaut:"
        echo "  - 50 patients"
        echo "  - 24h continues"
        echo "  - PostgreSQL localhost:5432/kidjamo"
        echo "  - Dashboard Streamlit sur port 8501"
        echo "  - Notifications SMS/Email activées"
        echo ""
        echo "Pour personnaliser, éditez config/massive_simulation_config.json"
        echo ""
        exit 0
        ;;
    --quick-test)
        PATIENTS=5
        DURATION=0.5
        echo "Mode test rapide: 5 patients, 30 minutes"
        ;;
esac

# Vérification dépendances
echo "Vérification dépendances Python..."
pip install -q streamlit plotly pandas psycopg2-binary twilio kafka-python requests

# Démarrage simulation
echo ""
echo "Démarrage simulation avec:"
echo "  - Patients: $PATIENTS"
echo "  - Durée: ${DURATION}h"
echo "  - Base: $DB_HOST:$DB_PORT/$DB_NAME"
echo ""
echo "Dashboard sera disponible sur: http://localhost:8501"
echo "SMS envoyés vers: +237695607089"
echo "Emails envoyés vers: christianouragan@gmail.com"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter la simulation"
echo ""

python3 massive_simulation_integration.py \
    --patients $PATIENTS \
    --duration $DURATION \
    --db-host $DB_HOST \
    --db-port $DB_PORT \
    --db-name $DB_NAME \
    --db-user $DB_USER \
    --db-password $DB_PASSWORD \
    --test-alerts
