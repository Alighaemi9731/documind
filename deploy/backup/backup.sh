#!/usr/bin/env bash
# DocuMind backup: Postgres dump + uploads + caddy_data (ACME certs).
# Usage: deploy/backup/backup.sh   (run from anywhere; resolves repo root)
#
# Each artifact is written to a *.partial file, integrity-checked, then atomically
# renamed into place — so a failed/truncated dump never becomes a "real" backup
# (and therefore never evicts a good older one during rotation).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[ -f .env ] || { echo "[backup] no .env found in $ROOT" >&2; exit 1; }

# Read only what we need for the pg_dump args (no broad export of every secret).
# Compose interpolates the rest itself via --env-file.
envget() { grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//' || true; }
PGUSER="$(envget POSTGRES_USER)"; PGUSER="${PGUSER:-documind}"
PGDB="$(envget POSTGRES_DB)";     PGDB="${PGDB:-documind}"

if docker compose version >/dev/null 2>&1; then COMPOSE=(docker compose --env-file .env -f deploy/docker-compose.yml)
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE=(docker-compose --env-file .env -f deploy/docker-compose.yml)
else echo "[backup] docker compose not found" >&2; exit 1; fi

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR:-$ROOT/backups}"
KEEP="${BACKUP_KEEP:-7}"
mkdir -p "$OUT"

echo "[backup] pg_dump -> db-$STAMP.dump.gz"
DB_PART="$OUT/db-$STAMP.dump.gz.partial"
if ! "${COMPOSE[@]}" exec -T postgres pg_dump -Fc -U "$PGUSER" "$PGDB" | gzip > "$DB_PART"; then
  rm -f "$DB_PART"
  echo "[backup] pg_dump FAILED — no dump written, existing backups untouched" >&2
  exit 1
fi
gzip -t "$DB_PART" || { rm -f "$DB_PART"; echo "[backup] dump failed gzip integrity check" >&2; exit 1; }
mv "$DB_PART" "$OUT/db-$STAMP.dump.gz"

echo "[backup] volumes (uploads + caddy_data) -> volumes-$STAMP.tar.gz"
VOL_PART="$OUT/volumes-$STAMP.tar.gz.partial"
if ! docker run --rm \
  -v documind_uploads:/uploads:ro \
  -v documind_caddy_data:/caddy:ro \
  -v "$OUT":/out \
  alpine tar czf "/out/$(basename "$VOL_PART")" -C / uploads caddy; then
  rm -f "$VOL_PART"
  echo "[backup] volume archive FAILED" >&2
  exit 1
fi
gzip -t "$VOL_PART" || { rm -f "$VOL_PART"; echo "[backup] volume archive failed gzip integrity check" >&2; exit 1; }
mv "$VOL_PART" "$OUT/volumes-$STAMP.tar.gz"

echo "[backup] rotating (keep $KEEP)"
ls -1t "$OUT"/db-*.dump.gz       2>/dev/null | tail -n +"$((KEEP+1))" | xargs -r rm -f
ls -1t "$OUT"/volumes-*.tar.gz   2>/dev/null | tail -n +"$((KEEP+1))" | xargs -r rm -f

echo "[backup] done -> $OUT"
