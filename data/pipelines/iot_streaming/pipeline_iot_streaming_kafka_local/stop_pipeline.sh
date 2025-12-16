#!/bin/bash
# Script d'arrêt pour pipeline IoT streaming Kidjamo
# Usage: ./stop_pipeline.sh

set -e

echo "🛑 Stopping Kidjamo IoT Streaming Pipeline..."

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Arrêt du simulateur
stop_simulator() {
    if [ -f "logs/simulator.pid" ]; then
        SIMULATOR_PID=$(cat logs/simulator.pid)
        if ps -p $SIMULATOR_PID > /dev/null; then
            log_info "Stopping IoT Simulator (PID: $SIMULATOR_PID)..."
            kill $SIMULATOR_PID
            sleep 2
            log_success "Simulator stopped"
        fi
        rm -f logs/simulator.pid
    fi
}

# Arrêt du streaming
stop_streaming() {
    if [ -f "logs/streaming.pid" ]; then
        STREAMING_PID=$(cat logs/streaming.pid)
        if ps -p $STREAMING_PID > /dev/null; then
            log_info "Stopping PySpark Streaming (PID: $STREAMING_PID)..."
            kill $STREAMING_PID
            sleep 5
            log_success "Streaming stopped"
        fi
        rm -f logs/streaming.pid
    fi
}

# Arrêt de l'API
stop_api() {
    if [ -f "logs/api.pid" ]; then
        API_PID=$(cat logs/api.pid)
        if ps -p $API_PID > /dev/null; then
            log_info "Stopping API (PID: $API_PID)..."
            kill $API_PID
            sleep 2
            log_success "API stopped"
        fi
        rm -f logs/api.pid
    fi
}

# Arrêt de Kafka
stop_kafka() {
    log_info "Stopping Kafka infrastructure..."
    cd kafka
    docker-compose down
    log_success "Kafka stopped"
    cd ..
}

# Nettoyage optionnel
cleanup_data() {
    if [ "$1" = "--clean-data" ]; then
        log_warning "Cleaning data lake..."
        rm -rf data_lake/raw/*
        rm -rf data_lake/bronze/*
        rm -rf data_lake/silver/*
        rm -rf checkpoints/*
        log_success "Data cleaned"
    fi
}

# Fonction principale
main() {
    echo "=================================================="
    echo "🛑 Kidjamo IoT Pipeline Shutdown"
    echo "=================================================="

    stop_simulator
    stop_streaming
    stop_api
    stop_kafka
    cleanup_data "$@"

    log_success "Pipeline stopped successfully!"
    echo ""
    echo "💡 Options:"
    echo "  • ./stop_pipeline.sh --clean-data (remove all data)"
    echo "  • ./start_pipeline.sh (restart pipeline)"
}

main "$@"
