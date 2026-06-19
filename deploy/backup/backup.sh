#!/usr/bin/env bash
# DocuMind backup: Postgres dump + uploads + caddy_data (ACME certs).
# Usage: deploy/backup/backup.sh   (run from anywhere; resolves repo root)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

COMPOSE=(docker compose --env-file .env -f deploy/docker-compose.yml)
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR:-$ROOT/backups}"
KEEP="${BACKUP_KEEP:-7}"
mkdir -p "$OUT"

echo "[backup] pg_dump -> db-$STAMP.dump.gz"
"${COMPOSE[@]}" exec -T postgres pg_dump -Fc -U "${POSTGRES_USER:-documind}" "${POSTGRES_DB:-documind}" \
  | gzip > "$OUT/db-$STAMP.dump.gz"

echo "[backup] volumes (uploads + caddy_data) -> volumes-$STAMP.tar.gz"
docker run --rm \
  -v documind_uploads:/uploads:ro \
  -v documind_caddy_data:/caddy:ro \
  -v "$OUT":/out \
  alpine tar czf "/out/volumes-$STAMP.tar.gz" -C / uploads caddy

echo "[backup] rotating (keep $KEEP)"
ls -1t "$OUT"/db-*.dump.gz       2>/dev/null | tail -n +"$((KEEP+1))" | xargs -r rm -f
ls -1t "$OUT"/volumes-*.tar.gz   2>/dev/null | tail -n +"$((KEEP+1))" | xargs -r rm -f

echo "[backup] done -> $OUT"
