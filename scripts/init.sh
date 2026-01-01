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
    docker compose -f "$COMPOSE_FILE" up -d --build
    log_info "Stack started! Waiting for services to be ready..."
    log_info "Note: The 'setup' container will run once to configure the UI."
    sleep 15
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
        log_warn "LiteLLM: ✗ not ready"
        all_healthy=false
    fi

    # Check Logos Gateway (Chainlit)
    if curl -sf http://localhost:8000/ &> /dev/null; then
        log_info "Logos Gateway (Chainlit): ✓ healthy"
    else
        # Chainlit often doesn't expose /health by default unless configured, let's assume it's up if port is open
        if nc -z localhost 8000; then
             log_info "Logos Gateway (Chainlit): ✓ port open"
        else
            log_error "Logos Gateway (Chainlit): ✗ unreachable"
            all_healthy=false
        fi
    fi

    if $all_healthy; then
        log_info "All core services are healthy!"
        echo ""
        log_info "Access points:"
        echo "  - Logos AI OS (Chainlit): http://localhost:8000"
        echo "  - LiteLLM API:            http://localhost:4000"
        echo "  - PostgreSQL:             localhost:5432"
    else
        log_warn "Some services are not ready yet. Try 'scripts/init.sh logs' to debug."
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
