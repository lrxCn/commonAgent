#!/usr/bin/env bash
# One-shot local dev stack: OrbStack/Docker infra → Agent → Back → Front.
#
# Usage:
#   ./dev.sh          # same as ./dev.sh up
#   ./dev.sh up       # start infra + app services
#   ./dev.sh down     # stop app services (keep Docker containers)
#   ./dev.sh down --all   # also stop Docker containers
#   ./dev.sh status   # show infra + app health
#   ./dev.sh logs [agent|back|front|all]
#
# Prerequisites: uv, pnpm (or npm), agent/.env, back/.env configured.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_DIR="$ROOT/.dev"
COMPOSE_FILE="$ROOT/docker-compose.dev.yml"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-my-postgres}"
QDRANT_CONTAINER="${QDRANT_CONTAINER:-qdrant_rag}"

AGENT_PORT="${AGENT_PORT:-18080}"
BACK_PORT="${BACK_PORT:-8080}"
FRONT_PORT="${FRONT_PORT:-5173}"

mkdir -p "$DEV_DIR"

log() { printf '[dev] %s\n' "$*"; }
warn() { printf '[dev][warn] %s\n' "$*" >&2; }
die() { printf '[dev][error] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

container_exists() {
  docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$1"
}

container_running() {
  docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"
}

ensure_orbstack() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  log "Docker not ready; starting OrbStack..."
  if command -v orbctl >/dev/null 2>&1; then
    orbctl start
  elif command -v orb >/dev/null 2>&1; then
    orb start
  else
    die "Docker is unavailable and orbctl/orb was not found. Start OrbStack manually."
  fi
  for _ in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
      log "Docker engine is ready."
      return 0
    fi
    sleep 1
  done
  die "Timed out waiting for Docker after starting OrbStack."
}

start_compose_service() {
  docker compose -f "$COMPOSE_FILE" up -d "$1"
}

start_infra() {
  ensure_orbstack

  local pg_exists qdrant_exists
  pg_exists=false
  qdrant_exists=false
  container_exists "$POSTGRES_CONTAINER" && pg_exists=true
  container_exists "$QDRANT_CONTAINER" && qdrant_exists=true

  if $pg_exists && $qdrant_exists; then
    log "Starting existing containers: $POSTGRES_CONTAINER, $QDRANT_CONTAINER"
    docker start "$POSTGRES_CONTAINER" "$QDRANT_CONTAINER" >/dev/null
  elif ! $pg_exists && ! $qdrant_exists; then
    log "Creating infra via docker compose..."
    docker compose -f "$COMPOSE_FILE" up -d
  else
    warn "Only one infra container exists; trying compose for missing service(s)."
    docker compose -f "$COMPOSE_FILE" up -d
    container_exists "$POSTGRES_CONTAINER" && docker start "$POSTGRES_CONTAINER" >/dev/null 2>&1 || true
    container_exists "$QDRANT_CONTAINER" && docker start "$QDRANT_CONTAINER" >/dev/null 2>&1 || true
  fi

  wait_postgres
  wait_qdrant
  ensure_back_database
}

wait_postgres() {
  log "Waiting for Postgres ($POSTGRES_CONTAINER)..."
  for _ in $(seq 1 60); do
    if container_running "$POSTGRES_CONTAINER" \
      && docker exec "$POSTGRES_CONTAINER" pg_isready -U postgres -q >/dev/null 2>&1; then
      log "Postgres is ready."
      return 0
    fi
    sleep 1
  done
  die "Postgres did not become ready in time."
}

wait_qdrant() {
  log "Waiting for Qdrant ($QDRANT_CONTAINER)..."
  for _ in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:6333/readyz" >/dev/null 2>&1 \
      || curl -sf "http://127.0.0.1:6333/" >/dev/null 2>&1; then
      log "Qdrant is ready."
      return 0
    fi
    sleep 1
  done
  die "Qdrant did not become ready in time."
}

ensure_back_database() {
  local exists
  exists="$(docker exec "$POSTGRES_CONTAINER" psql -U postgres -Atqc \
    "SELECT 1 FROM pg_database WHERE datname='common_agent_back'" 2>/dev/null || true)"
  if [[ "$exists" != "1" ]]; then
    log "Creating database common_agent_back..."
    docker exec "$POSTGRES_CONTAINER" psql -U postgres -c "CREATE DATABASE common_agent_back;" >/dev/null
  fi
}

pid_alive() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] || return 1
  local pid
  pid="$(cat "$pidfile")"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

stop_service() {
  local name="$1"
  local pidfile="$DEV_DIR/${name}.pid"
  if pid_alive "$pidfile"; then
    local pid
    pid="$(cat "$pidfile")"
    log "Stopping $name (pid $pid)..."
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.2
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}

start_bg() {
  local name="$1"
  local dir="$2"
  shift 2
  local pidfile="$DEV_DIR/${name}.pid"
  local logfile="$DEV_DIR/${name}.log"

  if pid_alive "$pidfile"; then
    log "$name already running (pid $(cat "$pidfile"))."
    return 0
  fi

  log "Starting $name → $logfile"
  (
    cd "$dir"
    exec "$@"
  ) >>"$logfile" 2>&1 &
  echo $! >"$pidfile"
}

wait_service_http() {
  local name="$1"
  local url="$2"
  local pidfile="$DEV_DIR/${name}.pid"
  local logfile="$DEV_DIR/${name}.log"

  for _ in $(seq 1 90); do
    if [[ -f "$pidfile" ]]; then
      local pid
      pid="$(cat "$pidfile")"
      if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
        die "${name} exited before becoming ready. Last lines of ${logfile}:
$(tail -n 25 "$logfile" 2>/dev/null || echo '(log empty)')"
      fi
    fi
    if curl -sf "$url" >/dev/null 2>&1; then
      log "$name is up: $url"
      return 0
    fi
    sleep 1
  done

  die "${name} did not respond at ${url}. See ${logfile}:
$(tail -n 25 "$logfile" 2>/dev/null || echo '(log empty)')"
}

prepare_back() {
  require_cmd uv
  [[ -f "$ROOT/back/.env" ]] || die "Missing back/.env — copy from back/.env.example and configure."
  log "Back migrations + seed..."
  (cd "$ROOT/back" && uv sync --quiet && uv run alembic upgrade head && uv run python -m db.seed)
}

prepare_agent() {
  require_cmd uv
  [[ -f "$ROOT/agent/.env" ]] || die "Missing agent/.env — copy from agent/.env.example and configure."
  log "Agent deps (uv sync)..."
  (cd "$ROOT/agent" && uv sync --quiet)
}

prepare_front() {
  if command -v pnpm >/dev/null 2>&1; then
    (cd "$ROOT/front" && pnpm install --silent)
  elif command -v npm >/dev/null 2>&1; then
    (cd "$ROOT/front" && npm install --silent)
  else
    die "Missing pnpm or npm for front/"
  fi

  # Rollup/Vite native bindings break after copy or Node upgrade; verify once.
  if ! (cd "$ROOT/front" && pnpm exec vite --version >/dev/null 2>&1); then
    warn "front native deps look broken; reinstalling node_modules..."
    rm -rf "$ROOT/front/node_modules"
    if command -v pnpm >/dev/null 2>&1; then
      (cd "$ROOT/front" && pnpm install)
    else
      (cd "$ROOT/front" && npm install)
    fi
  fi
}

start_apps() {
  prepare_agent
  prepare_back
  prepare_front

  start_bg agent "$ROOT/agent" \
    uv run uvicorn src.main:app --host 127.0.0.1 --port "$AGENT_PORT"

  start_bg back "$ROOT/back" \
    uv run uvicorn src.main:app --host 127.0.0.1 --port "$BACK_PORT"

  if command -v pnpm >/dev/null 2>&1; then
    start_bg front "$ROOT/front" pnpm dev --host 127.0.0.1 --port "$FRONT_PORT"
  else
    start_bg front "$ROOT/front" npm run dev -- --host 127.0.0.1 --port "$FRONT_PORT"
  fi

  wait_service_http agent "http://127.0.0.1:${AGENT_PORT}/health"
  wait_service_http back "http://127.0.0.1:${BACK_PORT}/health"
  wait_service_http front "http://127.0.0.1:${FRONT_PORT}/"

  cat <<EOF

========================================
commonAgent dev stack is running

  Front : http://127.0.0.1:${FRONT_PORT}
  Back  : http://127.0.0.1:${BACK_PORT}/health
  Agent : http://127.0.0.1:${AGENT_PORT}/health

  Logs  : ./dev.sh logs [agent|back|front|all]
  Stop  : ./dev.sh down
========================================

EOF
}

cmd_up() {
  start_infra
  start_apps
}

cmd_down() {
  stop_service agent
  stop_service back
  stop_service front

  if [[ "${1:-}" == "--all" ]]; then
    log "Stopping Docker containers..."
    docker stop "$POSTGRES_CONTAINER" "$QDRANT_CONTAINER" >/dev/null 2>&1 || true
  fi

  log "App services stopped."
}

cmd_status() {
  ensure_orbstack

  printf '\n--- Docker ---\n'
  for c in "$POSTGRES_CONTAINER" "$QDRANT_CONTAINER"; do
    if container_running "$c"; then
      printf '  [up]   %s\n' "$c"
    elif container_exists "$c"; then
      printf '  [down] %s\n' "$c"
    else
      printf '  [missing] %s\n' "$c"
    fi
  done

  printf '\n--- Apps ---\n'
  for name in agent back front; do
    local pidfile="$DEV_DIR/${name}.pid"
    if pid_alive "$pidfile"; then
      printf '  [up]   %s (pid %s) log: .dev/%s.log\n' "$name" "$(cat "$pidfile")" "$name"
    else
      printf '  [down] %s\n' "$name"
    fi
  done

  printf '\n--- HTTP ---\n'
  for item in \
    "Agent|http://127.0.0.1:${AGENT_PORT}/health" \
    "Back|http://127.0.0.1:${BACK_PORT}/health" \
    "Front|http://127.0.0.1:${FRONT_PORT}/"; do
    local label="${item%%|*}"
    local url="${item##*|}"
    if curl -sf "$url" >/dev/null 2>&1; then
      printf '  [ok]   %s %s\n' "$label" "$url"
    else
      printf '  [fail] %s %s\n' "$label" "$url"
    fi
  done
  printf '\n'
}

cmd_logs() {
  local target="${1:-all}"
  case "$target" in
    agent|back|front)
      tail -n 80 -f "$DEV_DIR/${target}.log"
      ;;
    all)
      tail -n 40 -f "$DEV_DIR/agent.log" "$DEV_DIR/back.log" "$DEV_DIR/front.log"
      ;;
    *)
      die "Unknown logs target: $target (use agent|back|front|all)"
      ;;
  esac
}

main() {
  local cmd="${1:-up}"
  shift || true

  case "$cmd" in
    up|start)
      cmd_up
      ;;
    down|stop)
      cmd_down "${1:-}"
      ;;
    status)
      cmd_status
      ;;
    logs)
      cmd_logs "${1:-all}"
      ;;
    restart)
      cmd_down
      cmd_up
      ;;
    -h|--help|help)
      sed -n '2,12p' "$0"
      ;;
    *)
      die "Unknown command: $cmd (try: up | down | status | logs | restart)"
      ;;
  esac
}

main "$@"
