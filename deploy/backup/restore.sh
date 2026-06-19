#!/usr/bin/env bash
# DocuMind restore. Usage:
#   deploy/backup/restore.sh <db-*.dump.gz> <volumes-*.tar.gz>
#
# DESTRUCTIVE — overwrites the database, the uploads volume, and caddy_data
# (ACME certs). Requires an interactive "yes" unless RESTORE_YES=1 is set
# (for automation). Both input files are validated BEFORE anything is touched.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[ -f .env ] || { echo "[restore] no .env found in $ROOT" >&2; exit 1; }

envget() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//' || true; }
PGUSER="$(envget POSTGRES_USER)"; PGUSER="${PGUSER:-documind}"
PGDB="$(envget POSTGRES_DB)";     PGDB="${PGDB:-documind}"

if docker compose version >/dev/null 2>&1; then COMPOSE=(docker compose --env-file .env -f deploy/docker-compose.yml)
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE=(docker-compose --env-file .env -f deploy/docker-compose.yml)
else echo "[restore] docker compose not found" >&2; exit 1; fi

DB="${1:?usage: restore.sh <db.dump.gz> <volumes.tar.gz>}"
VOL="${2:?usage: restore.sh <db.dump.gz> <volumes.tar.gz>}"

# Validate BOTH inputs before any destructive step (a typo must not wipe volumes
# and then fail on the DB).
[ -f "$DB" ]  || { echo "[restore] db backup not found: $DB" >&2; exit 1; }
[ -f "$VOL" ] || { echo "[restore] volumes backup not found: $VOL" >&2; exit 1; }
gzip -t "$DB"  || { echo "[restore] db backup is not a valid gzip: $DB" >&2; exit 1; }
gzip -t "$VOL" || { echo "[restore] volumes backup is not a valid gzip: $VOL" >&2; exit 1; }
VOL_DIR="$(cd "$(dirname "$VOL")" && pwd)"
VOL_FILE="$(basename "$VOL")"

if [ -z "${RESTORE_YES:-}" ]; then
  printf '\nThis will OVERWRITE the database, uploads, and TLS certs from:\n  %s\n  %s\nType "yes" to continue: ' "$DB" "$VOL"
  ans=""
  if [ -e /dev/tty ]; then read -r ans </dev/tty || true; else read -r ans || true; fi
  [ "$ans" = "yes" ] || { echo "[restore] aborted."; exit 1; }
fi

echo "[restore] stopping api + caddy"
"${COMPOSE[@]}" stop api caddy >/dev/null 2>&1 || true

echo "[restore] restoring volumes (clears uploads + caddy_data, then extracts)"
docker run --rm \
  -v documind_uploads:/uploads \
  -v documind_caddy_data:/caddy \
  -v "$VOL_DIR":/in:ro \
  alpine sh -c "set -e; rm -rf /uploads/* /uploads/.[!.]* /caddy/* /caddy/.[!.]* 2>/dev/null || true; cd / && tar xzf /in/$VOL_FILE"

echo "[restore] restoring database (pg_restore --clean)"
gunzip -c "$DB" | "${COMPOSE[@]}" exec -T postgres \
  pg_restore --clean --if-exists -U "$PGUSER" -d "$PGDB"

echo "[restore] starting api + caddy"
"${COMPOSE[@]}" start api caddy >/dev/null 2>&1 || true

echo "[restore] done"
