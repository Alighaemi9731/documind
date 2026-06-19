#!/usr/bin/env bash
# DocuMind restore. Usage:
#   deploy/backup/restore.sh <db-*.dump.gz> <volumes-*.tar.gz>
# Stops the API while restoring the database. Destructive — confirm before use.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE=(docker compose --env-file .env -f deploy/docker-compose.yml)
DB="${1:?usage: restore.sh <db.dump.gz> <volumes.tar.gz>}"
VOL="${2:?usage: restore.sh <db.dump.gz> <volumes.tar.gz>}"
VOL_DIR="$(cd "$(dirname "$VOL")" && pwd)"
VOL_FILE="$(basename "$VOL")"

echo "[restore] restoring volumes (uploads + caddy_data)"
docker run --rm \
  -v documind_uploads:/uploads \
  -v documind_caddy_data:/caddy \
  -v "$VOL_DIR":/in:ro \
  alpine sh -c "cd / && tar xzf /in/$VOL_FILE"

echo "[restore] restoring database (pg_restore --clean)"
"${COMPOSE[@]}" stop api >/dev/null 2>&1 || true
gunzip -c "$DB" | "${COMPOSE[@]}" exec -T postgres \
  pg_restore --clean --if-exists -U "${POSTGRES_USER:-documind}" -d "${POSTGRES_DB:-documind}"
"${COMPOSE[@]}" start api >/dev/null 2>&1 || true

echo "[restore] done"
