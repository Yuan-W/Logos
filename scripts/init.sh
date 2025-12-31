#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")/infra"
COMPOSE_FILE="$INFRA_DIR/docker-compose.yml"

# Helper functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available"
        exit 1
    fi
}

cmd_up() {
    log_info "Starting Logos AI stack..."
    docker compose -f "$COMPOSE_FILE" up -d
    log_info "Stack started! Waiting for services to be ready..."
    sleep 20
    cmd_health
}

cmd_down() {
    log_info "Stopping Logos AI stack..."
    docker compose -f "$COMPOSE_FILE" down
    log_info "Stack stopped."
}

cmd_logs() {
    docker compose -f "$COMPOSE_FILE" logs -f
}

cmd_health() {
    log_info "Checking service health..."
    local all_healthy=true

    # Check PostgreSQL
    if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U postgres &> /dev/null; then
        log_info "PostgreSQL: ✓ healthy"
    else
        log_error "PostgreSQL: ✗ unhealthy"
        all_healthy=false
    fi

    # Check LiteLLM (requires API key)
    if curl -sf -H "Authorization: Bearer sk-litellm-master-key" http://localhost:4000/health &> /dev/null; then
        log_info "LiteLLM: ✓ healthy"
    else
        log_warn "LiteLLM: ✗ not ready (may still be starting)"
        all_healthy=false
    fi

    # Check Open WebUI
    if curl -sf http://localhost:3000/health &> /dev/null; then
        log_info "Open WebUI: ✓ healthy"
    else
        log_warn "Open WebUI: ✗ not ready (may still be starting)"
        all_healthy=false
    fi

    if $all_healthy; then
        log_info "All services are healthy!"
        echo ""
        log_info "Access points:"
        echo "  - Open WebUI:  http://localhost:3000"
        echo "  - LiteLLM API: http://localhost:4000"
        echo "  - PostgreSQL:  localhost:5432"
    else
        log_warn "Some services are not ready yet. Try again in a few seconds."
    fi
}

cmd_status() {
    docker compose -f "$COMPOSE_FILE" ps
}

usage() {
    echo "Logos AI Infrastructure Management"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  up      Start all services"
    echo "  down    Stop all services"
    echo "  health  Check health of all services"
    echo "  logs    Tail logs from all services"
    echo "  status  Show status of all containers"
    echo ""
}

# Main
check_docker

case "${1:-}" in
    up)     cmd_up ;;
    down)   cmd_down ;;
    health) cmd_health ;;
    logs)   cmd_logs ;;
    status) cmd_status ;;
    *)      usage ;;
esac
