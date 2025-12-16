#!/bin/bash
# Script de démarrage complet pour pipeline IoT streaming Kidjamo
# Usage: ./start_pipeline.sh

set -e

echo "🚀 Starting Kidjamo IoT Streaming Pipeline..."

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Fonction utilitaire
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Vérification des prérequis
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is required but not installed"
        exit 1
    fi

    # Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is required but not installed"
        exit 1
    fi

    # Python
    if ! command -v python &> /dev/null; then
        log_error "Python is required but not installed"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Installation des dépendances Python
install_dependencies() {
    log_info "Installing Python dependencies..."

    if [ ! -d "venv" ]; then
        python -m venv venv
        log_success "Created virtual environment"
    fi

    source venv/bin/activate || source venv/Scripts/activate
    pip install -r requirements.txt

    log_success "Dependencies installed"
}

# Démarrage de Kafka
start_kafka() {
    log_info "Starting Kafka infrastructure..."

    cd kafka
    docker-compose up -d

    # Attendre que Kafka soit prêt
    log_info "Waiting for Kafka to be ready..."
    sleep 30

    # Vérifier les topics
    docker exec kidjamo-kafka kafka-topics --bootstrap-server localhost:9092 --list

    log_success "Kafka infrastructure started"
    cd ..
}

# Démarrage de l'API
start_api() {
    log_info "Starting IoT Ingestion API..."

    source venv/bin/activate || source venv/Scripts/activate

    cd api
    nohup python iot_ingestion_api.py > ../logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > ../logs/api.pid

    log_success "API started (PID: $API_PID)"
    cd ..

    # Test de santé de l'API
    sleep 5
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        log_success "API health check passed"
    else
        log_warning "API health check failed"
    fi
}

# Démarrage du streaming
start_streaming() {
    log_info "Starting PySpark Streaming..."

    source venv/bin/activate || source venv/Scripts/activate

    cd streaming
    nohup python iot_streaming_processor.py > ../logs/streaming.log 2>&1 &
    STREAMING_PID=$!
    echo $STREAMING_PID > ../logs/streaming.pid

    log_success "Streaming started (PID: $STREAMING_PID)"
    cd ..
}

# Démarrage du simulateur (optionnel)
start_simulator() {
    if [ "$1" = "--with-simulator" ]; then
        log_info "Starting IoT Simulator..."

        source venv/bin/activate || source venv/Scripts/activate

        cd simulator
        nohup python medical_iot_simulator.py > ../logs/simulator.log 2>&1 &
        SIMULATOR_PID=$!
        echo $SIMULATOR_PID > ../logs/simulator.pid

        log_success "Simulator started (PID: $SIMULATOR_PID)"
        cd ..
    fi
}

# Création des répertoires de logs
create_log_directories() {
    mkdir -p logs
    mkdir -p data_lake/{raw,bronze,silver,gold}
    mkdir -p checkpoints

    log_success "Log directories created"
}

# Configuration de l'environnement
setup_environment() {
    if [ ! -f "config/.env" ]; then
        cp config/.env.example config/.env
        log_warning "Created .env file from example. Please review and adjust settings."
    fi
}

# Fonction principale
main() {
    echo "=================================================="
    echo "🏥 Kidjamo IoT Streaming Pipeline Startup"
    echo "=================================================="

    check_prerequisites
    create_log_directories
    setup_environment
    install_dependencies
    start_kafka
    start_api
    start_streaming
    start_simulator "$@"

    echo ""
    log_success "Pipeline started successfully!"
    echo ""
    echo "📊 Access points:"
    echo "  • API Documentation: http://localhost:8001/docs"
    echo "  • API Health: http://localhost:8001/health"
    echo "  • Kafka UI: http://localhost:8090"
    echo ""
    echo "📁 Data locations:"
    echo "  • Raw data: ./data_lake/raw/"
    echo "  • Bronze data: ./data_lake/bronze/"
    echo "  • Logs: ./logs/"
    echo ""
    echo "🛑 To stop: ./stop_pipeline.sh"
    echo ""
}

# Gestion des signaux
trap 'log_warning "Received interrupt signal. Use ./stop_pipeline.sh to stop gracefully."; exit 1' INT TERM

# Exécution
main "$@"
