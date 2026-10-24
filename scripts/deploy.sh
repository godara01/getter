#!/usr/bin/env bash
# Run in the deployment directory. IMAGE must be an immutable GHCR SHA tag.
set -euo pipefail
: "${1:?usage: scripts/deploy.sh ghcr.io/OWNER/getter-api:sha-COMMIT}"
export GETTER_IMAGE="$1"
test -s .env.staging || { echo 'Missing .env.staging; deploy refused.' >&2; exit 1; }
compose() { docker compose --env-file .env.staging -f docker-compose.prod.yml "$@"; }
compose config --quiet
compose pull api worker redis caddy
# Migration failure stops deployment before changing running application containers.
compose run --rm --no-deps api alembic upgrade head
compose up -d --wait --wait-timeout 180
# Verify public TLS and readiness through Caddy after the containers restart.
domain=$(compose exec -T caddy printenv GETTER_API_DOMAIN)
curl --fail --silent --show-error --retry 12 --retry-all-errors --retry-delay 5 \
  --max-time 10 "https://${domain}/health/ready"
if test -f .current-image; then cp .current-image .previous-image; fi
printf '%s\n' "$GETTER_IMAGE" > .current-image
echo 'Staging deployment is healthy.'
