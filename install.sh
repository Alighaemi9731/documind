#!/usr/bin/env bash
#
# DocuMind one-line installer.
#
#   curl -fsSL https://raw.githubusercontent.com/Alighaemi9731/documind/main/install.sh | bash
#
# It is idempotent: re-running it PRESERVES generated secrets (so existing
# sessions and ACME certificates keep working) and only fills in what is
# missing. It never builds images on this host — it pulls public images from
# GHCR and brings the stack up with `docker compose`.
#
# Inputs (prompted interactively, or read from the environment for unattended
# installs — e.g. `DOMAIN=docs.example.com ADMIN_EMAIL=you@example.com bash install.sh`):
#   DOMAIN        apex domain pointed at this server (A/AAAA record)
#   ADMIN_EMAIL   bootstrap admin account + Let's Encrypt account email
#   GEMINI_KEY    optional free Gemini API key (seeds the shared default provider)
#
# Useful overrides:
#   DOCUMIND_DIR=/opt/documind            install/checkout directory
#   DOCUMIND_REPO_URL=…  DOCUMIND_REF=…   source repo + ref (clone path only)
#   IMAGE_OWNER=…  IMAGE_TAG=…            GHCR image coordinates
#   DOCUMIND_ACME_STAGING=1              use the LE *staging* CA (smoke tests)
#   DOCUMIND_SKIP_SWAP=1                 do not create a swapfile
#   DOCUMIND_ASSUME_YES=1               never prompt (fail if a required input is missing)
#
set -euo pipefail

# --------------------------------------------------------------------------- #
# Config (all overridable via env)
# --------------------------------------------------------------------------- #
REPO_URL="${DOCUMIND_REPO_URL:-https://github.com/Alighaemi9731/documind.git}"
REPO_REF="${DOCUMIND_REF:-main}"
INSTALL_DIR="${DOCUMIND_DIR:-/opt/documind}"
IMAGE_OWNER="${IMAGE_OWNER:-alighaemi9731}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
SWAP_SIZE_MB="${DOCUMIND_SWAP_MB:-2048}"
WAIT_TIMEOUT="${DOCUMIND_WAIT_TIMEOUT:-240}"

# --------------------------------------------------------------------------- #
# Pretty output (plain when not a TTY)
# --------------------------------------------------------------------------- #
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_B="\033[1m"; C_DIM="\033[2m"; C_G="\033[32m"; C_Y="\033[33m"; C_R="\033[31m"; C_0="\033[0m"
else
  C_B=""; C_DIM=""; C_G=""; C_Y=""; C_R=""; C_0=""
fi
log()  { printf "${C_G}==>${C_0} ${C_B}%s${C_0}\n" "$*"; }
info() { printf "    %s\n" "$*"; }
warn() { printf "${C_Y}warn:${C_0} %s\n" "$*" >&2; }
err()  { printf "${C_R}error:${C_0} %s\n" "$*" >&2; }
die()  { err "$*"; exit 1; }

# Interactive only when we have a controlling terminal AND were not told otherwise.
TTY=""
if [ -e /dev/tty ] && [ -z "${DOCUMIND_ASSUME_YES:-}" ]; then TTY="/dev/tty"; fi
prompt() { # prompt VAR "Question" "default"
  local __var="$1" __q="$2" __def="${3:-}" __ans=""
  if [ -z "$TTY" ]; then
    [ -n "$__def" ] && { printf -v "$__var" '%s' "$__def"; return 0; }
    die "missing required input '$__var' and no terminal to prompt (set it in the environment)"
  fi
  if [ -n "$__def" ]; then
    printf "${C_B}?${C_0} %s ${C_DIM}[%s]${C_0}: " "$__q" "$__def" >"$TTY"
  else
    printf "${C_B}?${C_0} %s: " "$__q" >"$TTY"
  fi
  IFS= read -r __ans <"$TTY" || true
  [ -z "$__ans" ] && __ans="$__def"
  printf -v "$__var" '%s' "$__ans"
}

# --------------------------------------------------------------------------- #
# Privilege + tooling
# --------------------------------------------------------------------------- #
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else
    warn "not root and 'sudo' not found — swapfile/fstab steps will be skipped if they need root"
  fi
fi

have() { command -v "$1" >/dev/null 2>&1; }

# docker (+ compose v2) detection; fall back to sudo if the socket needs it.
detect_docker() {
  have docker || die "Docker is not installed. See https://docs.docker.com/engine/install/"
  if docker info >/dev/null 2>&1; then DOCKER="docker";
  elif [ -n "$SUDO" ] && $SUDO docker info >/dev/null 2>&1; then DOCKER="$SUDO docker";
  else die "cannot talk to the Docker daemon (is it running? are you in the 'docker' group?)"; fi
  if $DOCKER compose version >/dev/null 2>&1; then COMPOSE_BASE="$DOCKER compose";
  elif have docker-compose; then COMPOSE_BASE="docker-compose";
  else die "Docker Compose v2 is required (the 'docker compose' plugin)."; fi
}
# Run a compose subcommand against our project.
dc() { $COMPOSE_BASE --env-file "$ENV_FILE" -f "$REPO_DIR/deploy/docker-compose.yml" "$@"; }

# --------------------------------------------------------------------------- #
# 1. Locate (or fetch) the repository
# --------------------------------------------------------------------------- #
locate_repo() {
  local src="${BASH_SOURCE[0]:-}"
  if [ -n "$src" ] && [ -f "$src" ] && [ -f "$(cd "$(dirname "$src")" && pwd)/deploy/docker-compose.yml" ]; then
    REPO_DIR="$(cd "$(dirname "$src")" && pwd)"
    log "Using local checkout: $REPO_DIR"
    return
  fi
  have git || die "git is required to fetch DocuMind (or run install.sh from a checkout)."
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating existing checkout: $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$REPO_REF" >/dev/null 2>&1 || warn "git fetch failed; using the checkout as-is"
    git -C "$INSTALL_DIR" checkout -q "$REPO_REF" 2>/dev/null || true
    git -C "$INSTALL_DIR" reset --hard "origin/$REPO_REF" >/dev/null 2>&1 || true
  else
    log "Cloning $REPO_URL ($REPO_REF) -> $INSTALL_DIR"
    $SUDO mkdir -p "$INSTALL_DIR" 2>/dev/null || mkdir -p "$INSTALL_DIR"
    [ -w "$INSTALL_DIR" ] || $SUDO chown -R "$(id -u):$(id -g)" "$INSTALL_DIR" 2>/dev/null || true
    git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$INSTALL_DIR"
  fi
  REPO_DIR="$INSTALL_DIR"
}

# --------------------------------------------------------------------------- #
# 2. Preflight checks (mostly soft — the real gate is `compose pull`)
# --------------------------------------------------------------------------- #
check_port_80() {
  local busy=""
  if have ss; then ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE '(^|[:.])80$' && busy=1 || true
  elif have netstat; then netstat -ltn 2>/dev/null | awk '{print $4}' | grep -qE '[:.]80$' && busy=1 || true; fi
  if [ -n "$busy" ]; then
    warn "something is already listening on port 80 — Caddy needs it for the Let's Encrypt HTTP-01 challenge."
  fi
}

check_ghcr_manifest() { # repo tag
  local repo="$1" tag="$2" token=""
  have curl || { warn "curl not found; skipping the GHCR image preflight"; return; }
  token="$(curl -fsSL "https://ghcr.io/token?scope=repository:${IMAGE_OWNER}/${repo}:pull" 2>/dev/null \
           | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' || true)"
  [ -z "$token" ] && { warn "could not obtain a GHCR token for ${repo}; the real check is the pull below"; return; }
  local code
  code="$(curl -fsS -o /dev/null -w '%{http_code}' -X GET \
           -H "Authorization: Bearer ${token}" \
           -H "Accept: application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json" \
           "https://ghcr.io/v2/${IMAGE_OWNER}/${repo}/manifests/${tag}" 2>/dev/null || true)"
  if [ "$code" = "200" ]; then info "image ghcr.io/${IMAGE_OWNER}/${repo}:${tag} ✓"
  else warn "ghcr.io/${IMAGE_OWNER}/${repo}:${tag} not reachable (HTTP ${code:-?}). 'docker compose pull' will report the real error."; fi
}

check_dns() { # domain
  local domain="$1" want="" got=""
  have curl || return 0
  want="$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if have getent; then got="$(getent ahostsv4 "$domain" 2>/dev/null | awk 'NR==1{print $1}' || true)"; fi
  { [ -z "$got" ] && have dig; } && got="$(dig +short A "$domain" 2>/dev/null | head -1 || true)" || true
  { [ -z "$got" ] && have host; } && got="$(host -t A "$domain" 2>/dev/null | awk '/has address/{print $4; exit}' || true)" || true
  if [ -n "$want" ] && [ -n "$got" ] && [ "$want" != "$got" ]; then
    warn "DNS: $domain -> ${got:-none}, but this host appears to be ${want}. HTTPS will fail until the A record points here."
  elif [ -z "$got" ]; then
    warn "DNS: could not resolve $domain yet — make sure its A/AAAA record points at this server before certificates can issue."
  fi
}

ensure_swap() {
  [ -n "${DOCUMIND_SKIP_SWAP:-}" ] && { info "swap: skipped (DOCUMIND_SKIP_SWAP set)"; return; }
  [ "$(uname -s)" = "Linux" ] || { info "swap: skipped (non-Linux host)"; return; }
  local mem_kb mem_mb swap_kb
  mem_kb="$(awk '/^MemTotal:/{print $2}' /proc/meminfo 2>/dev/null || echo 0)"
  swap_kb="$(awk '/^SwapTotal:/{print $2}' /proc/meminfo 2>/dev/null || echo 0)"
  mem_mb=$(( mem_kb / 1024 ))
  if [ "$mem_mb" -gt 2600 ]; then info "swap: ${mem_mb}MB RAM — swapfile not required"; return; fi
  if [ "$swap_kb" -ge $(( SWAP_SIZE_MB * 1024 )) ]; then info "swap: $(( swap_kb / 1024 ))MB already present"; return; fi
  if [ -z "$SUDO" ] && [ "$(id -u)" -ne 0 ]; then warn "swap: need root to create a swapfile; skipping (you should add one on a 2GB box)"; return; fi
  log "Creating a ${SWAP_SIZE_MB}MB swapfile (RAM is ${mem_mb}MB; required headroom for ingest + HNSW build)"
  local target_bytes=$(( SWAP_SIZE_MB * 1024 * 1024 ))
  if [ -e /swapfile ]; then
    # Reaching here means total swap is insufficient. If a correctly-sized
    # /swapfile already exists (just not enabled), enable it rather than destroy
    # and recreate a file we may not own.
    local cur; cur="$(stat -c %s /swapfile 2>/dev/null || stat -f %z /swapfile 2>/dev/null || echo 0)"
    if [ "${cur:-0}" -ge "$target_bytes" ]; then
      $SUDO swapon /swapfile 2>/dev/null || true
      info "swap: reused the existing ${SWAP_SIZE_MB}MB /swapfile"
      return 0
    fi
    $SUDO swapoff /swapfile 2>/dev/null || true; $SUDO rm -f /swapfile
  fi
  if have fallocate && $SUDO fallocate -l "${SWAP_SIZE_MB}M" /swapfile 2>/dev/null; then :; else
    $SUDO dd if=/dev/zero of=/swapfile bs=1M count="$SWAP_SIZE_MB" status=none
  fi
  $SUDO chmod 600 /swapfile
  $SUDO mkswap /swapfile >/dev/null || { warn "mkswap failed"; return 1; }
  $SUDO swapon /swapfile || { warn "swapon failed"; return 1; }
  if ! grep -q '^/swapfile ' /etc/fstab 2>/dev/null; then
    echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
  fi
  info "swap: ${SWAP_SIZE_MB}MB active and persisted in /etc/fstab"
}

# --------------------------------------------------------------------------- #
# 3. Secrets + .env (preserve on re-run)
# --------------------------------------------------------------------------- #
env_get() { # KEY  (reads existing $ENV_FILE; strips a trailing inline comment)
  # ALWAYS returns 0 — a missing file or absent key yields empty output, never a
  # non-zero status (which under `set -e` would abort the installer).
  [ -f "$ENV_FILE" ] || return 0
  local line
  line="$(grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 || true)"
  [ -n "$line" ] || return 0
  printf '%s' "${line#*=}" | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//'
}
keep_or() { local v; v="$(env_get "$1")"; [ -n "$v" ] && printf '%s' "$v" || printf '%s' "$2"; }

gen_hex()    { openssl rand -hex "${1:-32}"; }
gen_fernet() { openssl rand -base64 32 | tr '+/' '-_'; }  # 32 bytes, url-safe base64 == valid Fernet key

require_openssl() { have openssl || die "openssl is required to generate secrets."; }

write_env() {
  require_openssl
  # Preserve any existing secrets so a re-run never invalidates sessions/keys.
  local pg_pw jwt fernet gem reg prov max_mb domain admin acme_ca
  pg_pw="$(env_get POSTGRES_PASSWORD)";   [ -n "$pg_pw" ]  || pg_pw="$(gen_hex 24)"
  jwt="$(env_get JWT_SECRET)";            [ -n "$jwt" ]    || jwt="$(gen_hex 48)"
  fernet="$(env_get MASTER_KEY_FERNET)";  [ -n "$fernet" ] || fernet="$(gen_fernet)"
  # Inputs (new value wins; otherwise keep what's on disk).
  domain="${DOMAIN}"; admin="${ADMIN_EMAIL}"; gem="${GEMINI_KEY:-$(env_get OPERATOR_DEFAULT_GEMINI_KEY)}"
  reg="$(keep_or REGISTRATION_MODE open)"
  prov="$(keep_or DEFAULT_PROVIDER google)"
  max_mb="$(keep_or MAX_UPLOAD_MB 25)"
  acme_ca="https://acme-v02.api.letsencrypt.org/directory"
  [ -n "${DOCUMIND_ACME_STAGING:-}" ] && acme_ca="https://acme-staging-v02.api.letsencrypt.org/directory"

  umask 077
  cat > "$ENV_FILE" <<EOF
# DocuMind environment — generated by install.sh. Do NOT commit this file.
# Secrets are generated once and PRESERVED on re-run. No inline comments below
# (docker compose reads everything after '=' literally).
DOMAIN=$domain
ACME_EMAIL=$admin
ADMIN_EMAIL=$admin
PUBLIC_BASE_URL=https://$domain
ACME_CA=$acme_ca

IMAGE_OWNER=$IMAGE_OWNER
IMAGE_TAG=$IMAGE_TAG

POSTGRES_USER=documind
POSTGRES_PASSWORD=$pg_pw
POSTGRES_DB=documind
DATABASE_URL=postgresql+asyncpg://documind:$pg_pw@postgres:5432/documind

JWT_SECRET=$jwt
MASTER_KEY_FERNET=$fernet

OPERATOR_DEFAULT_GEMINI_KEY=$gem
DEFAULT_PROVIDER=$prov

REGISTRATION_MODE=$reg
MAX_UPLOAD_MB=$max_mb
INGEST_CONCURRENCY=$(keep_or INGEST_CONCURRENCY 1)
UPLOADS_DIR=/data/uploads
MAX_PENDING_INGEST_PER_USER=$(keep_or MAX_PENDING_INGEST_PER_USER 20)
ENABLE_LOCAL_EMBEDDINGS=$(keep_or ENABLE_LOCAL_EMBEDDINGS false)
GROUNDING_MIN_SCORE=$(keep_or GROUNDING_MIN_SCORE 0.55)
ACCESS_TOKEN_TTL_MINUTES=$(keep_or ACCESS_TOKEN_TTL_MINUTES 15)
REFRESH_TOKEN_TTL_DAYS=$(keep_or REFRESH_TOKEN_TTL_DAYS 30)
LOG_LEVEL=$(keep_or LOG_LEVEL info)
ENVIRONMENT=production
EOF
  chmod 600 "$ENV_FILE"
}

# --------------------------------------------------------------------------- #
# 4. Bring the stack up + initialize
# --------------------------------------------------------------------------- #
api_ready() { # poll readiness from INSIDE the api container (independent of DNS/TLS)
  dc exec -T api python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready',timeout=4).status==200 else 1)" >/dev/null 2>&1
}

wait_for() { # describe  function  timeout
  local what="$1" fn="$2" timeout="$3" waited=0
  printf "    waiting for %s" "$what"
  while ! "$fn"; do
    sleep 3; waited=$((waited+3)); printf "."
    if [ "$waited" -ge "$timeout" ]; then printf "\n"; return 1; fi
  done
  printf " ${C_G}ok${C_0}\n"
}

surface_https() { # domain — confirm the public cert, or print actionable ACME guidance
  local domain="$1" code
  have curl || { info "skip public HTTPS probe (curl missing)"; return; }
  code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 20 "https://$domain/api/health/ready" 2>/dev/null || true)"
  if [ "$code" = "200" ]; then
    log "HTTPS is live and trusted: https://$domain"
    return
  fi
  warn "could not reach https://$domain yet (HTTP ${code:-none})."
  info "This is usually DNS not yet pointing here, port 80 blocked, or ACME still in progress."
  info "Recent Caddy/ACME log lines:"
  dc logs --tail 25 caddy 2>/dev/null | sed 's/^/      /' || true
  info "Once DNS resolves to this host and ports 80/443 are open, Caddy issues the certificate automatically."
}

main() {
  printf "\n${C_B}DocuMind installer${C_0}\n\n"
  detect_docker
  locate_repo
  ENV_FILE="$REPO_DIR/.env"

  # ---- gather inputs (env first, then prompt, then preserved value) ----
  DOMAIN="${DOMAIN:-$(env_get DOMAIN)}"
  ADMIN_EMAIL="${ADMIN_EMAIL:-$(env_get ADMIN_EMAIL)}"
  [ "${DOMAIN:-}" = "docs.example.com" ] && DOMAIN=""
  [ "${ADMIN_EMAIL:-}" = "admin@example.com" ] && ADMIN_EMAIL=""
  prompt DOMAIN      "Domain pointed at this server (apex)" "${DOMAIN:-}"
  prompt ADMIN_EMAIL "Admin email (login + Let's Encrypt account)" "${ADMIN_EMAIL:-}"
  [ -n "$DOMAIN" ]      || die "a domain is required"
  [ -n "$ADMIN_EMAIL" ] || die "an admin email is required"
  # Validate the domain BEFORE it is written into .env / the Caddy config: only a
  # plain hostname (letters, digits, dots, hyphens) with at least one dot. This
  # also rejects whitespace/newlines that could otherwise inject extra .env lines.
  case "$DOMAIN" in
    *[!a-zA-Z0-9.-]* | -* | .* | *. | *..*) die "domain looks invalid: $DOMAIN" ;;
  esac
  [ "${DOMAIN%.*}" = "$DOMAIN" ] && die "use a fully-qualified domain, e.g. docs.example.com (got: $DOMAIN)"
  case "$ADMIN_EMAIL" in
    *[[:space:]]*) die "admin email must not contain whitespace: $ADMIN_EMAIL" ;;
    *@*.*) : ;;
    *) die "admin email looks invalid: $ADMIN_EMAIL" ;;
  esac
  if [ -z "${GEMINI_KEY:-}" ] && [ -z "$(env_get OPERATOR_DEFAULT_GEMINI_KEY)" ]; then
    prompt GEMINI_KEY "Free Gemini API key for the shared default (optional, Enter to skip)" ""
  fi
  # The key is pasted verbatim after '=' in the .env heredoc; reject embedded
  # whitespace/newlines so it can't inject an extra .env line (a real key has none).
  case "${GEMINI_KEY:-}" in *[[:space:]]*) die "the Gemini key must not contain spaces or newlines" ;; esac

  log "Preflight"
  # Soft checks: warn-only, never abort the install (the real gate is the pull).
  check_port_80 || true
  check_ghcr_manifest documind-api "$IMAGE_TAG" || true
  check_ghcr_manifest documind-web "$IMAGE_TAG" || true
  check_dns "$DOMAIN" || true
  ensure_swap || warn "swapfile setup did not complete — on a 2GB box add one manually (see docs/operating.md)"

  log "Writing $ENV_FILE (secrets preserved on re-run)"
  write_env

  log "Pulling images"
  dc pull

  log "Starting the stack"
  dc up -d --remove-orphans

  wait_for "PostgreSQL" "_pg_ready" 120 || die "PostgreSQL did not become healthy — see: $COMPOSE_BASE logs postgres"

  log "Applying database migrations"
  dc exec -T api alembic upgrade head

  if [ -n "${GEMINI_KEY:-}" ] || [ -n "$(env_get OPERATOR_DEFAULT_GEMINI_KEY)" ]; then
    log "Seeding the shared Gemini provider key"
    dc exec -T api python -m app.cli seed-operator-key || warn "operator-key seeding failed (you can add a key later in the admin dashboard)"
  else
    info "No Gemini key provided — add one in the admin dashboard (Settings → Operator key) to enable the free shared default."
  fi

  log "Ensuring the bootstrap admin account"
  dc exec -T api python -m app.cli bootstrap-admin --email "$ADMIN_EMAIL"

  wait_for "the API to report ready" "api_ready" "$WAIT_TIMEOUT" || warn "API readiness timed out — check: $COMPOSE_BASE logs api"

  printf "\n"
  surface_https "$DOMAIN"
  printf "\n${C_G}Done.${C_0} Open ${C_B}https://%s${C_0} and sign in / register with ${C_B}%s${C_0}.\n" "$DOMAIN" "$ADMIN_EMAIL"
  info "Re-run this script any time to upgrade — your secrets and data are preserved."
  info "Backups: deploy/backup/backup.sh   •   Runbook: docs/operating.md"
}

# postgres health via compose (named function so wait_for can call it)
_pg_ready() { dc exec -T postgres pg_isready -U documind -d documind >/dev/null 2>&1; }

main "$@"
