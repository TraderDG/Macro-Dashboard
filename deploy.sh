#!/usr/bin/env bash
# ── Macro Terminal — VPS Deploy Script ────────────────────────────────────────
# Usage:
#   First deploy:  bash deploy.sh --domain yourdomain.com --email you@email.com
#   Update:        bash deploy.sh --update
#
# Requirements: Ubuntu/Debian VPS with root access, domain A record pointing to VPS IP.

set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()     { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }

# ── Parse args ────────────────────────────────────────────────────────────────
DOMAIN=""
EMAIL=""
UPDATE_ONLY=false
REPO_URL="https://github.com/YOUR_GITHUB_USER/macro-dashboard.git"  # EDIT THIS
INSTALL_DIR="/opt/macro-dashboard"

while [[ $# -gt 0 ]]; do
  case $1 in
    --domain) DOMAIN="$2"; shift 2 ;;
    --email)  EMAIL="$2";  shift 2 ;;
    --update) UPDATE_ONLY=true; shift ;;
    --repo)   REPO_URL="$2"; shift 2 ;;
    --dir)    INSTALL_DIR="$2"; shift 2 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

# ── Update mode ───────────────────────────────────────────────────────────────
if $UPDATE_ONLY; then
  info "Pulling latest code and rebuilding..."
  cd "$INSTALL_DIR"
  git pull origin main
  docker compose -f docker-compose.prod.yml build --no-cache backend frontend
  docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend celery_worker celery_beat binance_consumer
  success "Update complete. Running at https://$(grep ^DOMAIN .env | cut -d= -f2)"
  exit 0
fi

# ── Validate ──────────────────────────────────────────────────────────────────
[[ -z "$DOMAIN" ]] && die "Missing --domain. Usage: bash deploy.sh --domain yourdomain.com --email you@email.com"
[[ -z "$EMAIL" ]]  && die "Missing --email. Required for Let's Encrypt."

info "Deploying Macro Terminal → https://$DOMAIN"

# ── 1. System dependencies ────────────────────────────────────────────────────
info "Installing Docker..."
if ! command -v docker &>/dev/null; then
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  success "Docker installed"
else
  success "Docker already installed"
fi

# ── 2. Clone / pull repo ──────────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "Repo exists — pulling latest..."
  git -C "$INSTALL_DIR" pull origin main
else
  info "Cloning repo..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# ── 3. Create .env ────────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  info "Creating .env from template..."
  cp .env.prod.example .env
  # Generate a random secret key
  SECRET=$(openssl rand -hex 32)
  # Generate strong DB password
  DB_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 28)

  sed -i "s/yourdomain\.com/$DOMAIN/g"                 .env
  sed -i "s/your@email\.com/$EMAIL/g"                  .env
  sed -i "s/CHANGE_THIS_STRONG_PASSWORD/$DB_PASS/g"    .env
  sed -i "s/CHANGE_THIS_SECRET_64_CHARS_RANDOM_STRING/$SECRET/g" .env

  warn "Review .env before continuing:"
  warn "  nano $INSTALL_DIR/.env"
  echo ""
  read -p "Press ENTER when ready to continue..." _
else
  success ".env already exists — using it"
fi

# Load DOMAIN from .env in case it was already set there
DOMAIN=$(grep ^DOMAIN .env | cut -d= -f2 | tr -d '"')

# ── 4. Build images ────────────────────────────────────────────────────────────
info "Building Docker images (this takes ~3-5 min)..."
docker compose -f docker-compose.prod.yml build

# ── 5. Start with HTTP-only nginx (for ACME challenge) ────────────────────────
info "Starting nginx in HTTP-only mode for certificate issuance..."
cp nginx/init.conf nginx/nginx.conf
docker compose -f docker-compose.prod.yml up -d nginx timescaledb redis

info "Waiting for nginx to start..."
sleep 5

# ── 6. Issue SSL certificate ──────────────────────────────────────────────────
info "Requesting Let's Encrypt certificate for $DOMAIN..."
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

success "SSL certificate issued!"

# ── 7. Switch to production nginx config ─────────────────────────────────────
info "Activating HTTPS nginx config..."
sed "s/__DOMAIN__/$DOMAIN/g" nginx/prod.conf.tmpl > nginx/nginx.conf
docker compose -f docker-compose.prod.yml restart nginx
sleep 3

# ── 8. Start all services ─────────────────────────────────────────────────────
info "Starting all services..."
docker compose -f docker-compose.prod.yml up -d

# ── 9. Wait for backend to be healthy ────────────────────────────────────────
info "Waiting for backend to become healthy..."
for i in $(seq 1 30); do
  if docker inspect macro_backend --format='{{.State.Health.Status}}' 2>/dev/null | grep -q healthy; then
    success "Backend healthy!"
    break
  fi
  echo -n "."
  sleep 5
done

# ── 10. Initial data seed ─────────────────────────────────────────────────────
info "Triggering initial data backfill (runs in background ~5 min)..."
docker compose -f docker-compose.prod.yml run --rm seeder || warn "Seeder already ran or failed — check logs"

# ── 11. Set up cert auto-renewal cron ─────────────────────────────────────────
info "Setting up certificate renewal cron..."
CRON_JOB="0 3 * * * cd $INSTALL_DIR && docker compose -f docker-compose.prod.yml run --rm certbot renew && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload"
(crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$CRON_JOB") | crontab -
success "Cert renewal scheduled at 03:00 daily"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Macro Terminal deployed successfully!          ║${NC}"
echo -e "${GREEN}║                                                  ║${NC}"
echo -e "${GREEN}║   https://$DOMAIN${NC}"
echo -e "${GREEN}║   API docs: https://$DOMAIN/docs                 ║${NC}"
echo -e "${GREEN}║                                                  ║${NC}"
echo -e "${GREEN}║   Useful commands:                               ║${NC}"
echo -e "${GREEN}║   docker compose -f docker-compose.prod.yml logs ║${NC}"
echo -e "${GREEN}║   bash deploy.sh --update  (deploy new version)  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
