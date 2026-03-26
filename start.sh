#!/usr/bin/env bash
# start.sh — Start the full GraphCRM stack (all services)
# Usage: ./start.sh [--no-logs]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

NO_LOGS=false
for arg in "$@"; do
  [[ "$arg" == "--no-logs" ]] && NO_LOGS=true
done

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}==>${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET}  $*"; }
warn()    { echo -e "${YELLOW}!${RESET}  $*"; }
error()   { echo -e "${RED}✗${RESET}  $*" >&2; }

# ── Preflight checks ──────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  error "Docker is not installed. Install Docker Desktop and retry."
  exit 1
fi

if ! docker info &>/dev/null; then
  error "Docker daemon is not running. Start Docker Desktop and retry."
  exit 1
fi

# ── Check .env file ───────────────────────────────────────────────────────────
if [[ ! -f "./.env" ]]; then
  if [[ -f "./.env.example" ]]; then
    warn ".env not found — copying from .env.example"
    cp "./.env.example" "./.env"
    warn "Edit ./.env and set ANTHROPIC_API_KEY before running LLM features."
  else
    warn ".env not found. Services will use default environment variables."
  fi
fi

# ── Build & start ─────────────────────────────────────────────────────────────
info "Building images and starting all services..."
docker compose up -d --build

# ── Wait for Django ───────────────────────────────────────────────────────────
info "Waiting for Django to be ready..."
MAX_WAIT=120
ELAPSED=0
until docker compose exec -T django python manage.py check &>/dev/null; do
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    error "Django did not start within ${MAX_WAIT}s. Check: docker compose logs django"
    exit 1
  fi
  printf '.'
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
echo ""
success "Django is up"

# ── Wait for Neo4j ─────────────────────────────────────────────────────────────
info "Waiting for Neo4j to be ready..."
ELAPSED=0
until docker compose exec -T django python -c "
from core.graph.driver import get_driver
d = get_driver(); d.verify_connectivity(); print('ok')
" &>/dev/null; do
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    warn "Neo4j did not start within ${MAX_WAIT}s — graph sync may fail."
    break
  fi
  printf '.'
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done
echo ""
success "Neo4j is up"

# ── Migrations ────────────────────────────────────────────────────────────────
info "Running database migrations..."
docker compose exec -T django python manage.py migrate --no-input
success "Migrations complete"

# ── Seed users ────────────────────────────────────────────────────────────────
info "Seeding team users (admin / alice / bob — password: password)..."
docker compose exec -T django python manage.py seed_users 2>/dev/null || true
success "Users seeded"

# ── Sync Neo4j graph ──────────────────────────────────────────────────────────
info "Syncing PostgreSQL data to Neo4j for graph visualization..."
docker compose exec -T django python manage.py resync_neo4j --confirm 2>/dev/null || true
success "Neo4j graph synced"

# ── Start RabbitMQ consumers ─────────────────────────────────────────────
info "Starting RabbitMQ lead consumer in the background..."
docker compose exec -T -d django python manage.py start_consumer
success "Lead consumer started"

# ── Service URLs ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}===========================================${RESET}"
echo -e "${BOLD}  GraphCRM is running${RESET}"
echo -e "${BOLD}===========================================${RESET}"
echo -e "  ${GREEN}Admin     ${RESET} http://localhost:8000/admin/"
echo -e "  ${GREEN}Django API${RESET} http://localhost:8000/api/"
echo -e "  ${GREEN}WebSocket ${RESET} ws://localhost:8000/ws/crm/"
echo -e "  ${GREEN}Neo4j     ${RESET} http://localhost:7474  (neo4j / password)"
echo -e "  ${GREEN}RabbitMQ  ${RESET} http://localhost:15672 (guest / guest)"
echo -e "  ${GREEN}ClickHouse${RESET} http://localhost:8123"
echo -e "${BOLD}===========================================${RESET}"
echo ""
echo -e "  ${YELLOW}Credentials${RESET}  admin / alice / bob — password: password"
echo ""
echo -e "  Useful commands:"
echo -e "    ${CYAN}make seed${RESET}        — simulate Bookkeeper events"
echo -e "    ${CYAN}make test${RESET}        — run backend test suite"
echo -e "    ${CYAN}make consumer${RESET}    — start RabbitMQ lead consumer"
echo -e "    ${CYAN}make llm-consumer${RESET} — start LLM tagging consumer"
echo -e "    ${CYAN}make down${RESET}        — stop all services"
echo ""

if [[ "$NO_LOGS" == "true" ]]; then
  success "All services started in the background."
else
  echo -e "  ${CYAN}Tailing logs${RESET} (Ctrl-C stops watching — services keep running)"
  echo ""
  docker compose logs -f django celery_worker celery_llm_worker
fi
