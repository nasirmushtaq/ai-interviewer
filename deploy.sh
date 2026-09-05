#!/usr/bin/env bash
# One-command deploy for the self-hosted Docker stack.
#   ./deploy.sh            -> build + start everything, install Piston runtimes
#   ./deploy.sh down       -> stop the stack
#   ./deploy.sh logs       -> tail logs
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"

cmd="${1:-up}"

case "$cmd" in
  down)  exec $COMPOSE down ;;
  logs)  exec $COMPOSE logs -f ;;
  ps)    exec $COMPOSE ps ;;
esac

if [ ! -f .env.prod ]; then
  echo "ERROR: .env.prod not found. Copy .env.prod.example -> .env.prod and edit it." >&2
  exit 1
fi

echo "==> Building and starting the stack..."
$COMPOSE up -d --build

echo "==> Waiting for Piston to be ready..."
sleep 8

echo "==> Installing code-execution runtimes (Python/Java/C++)..."
PISTON_CID="$($COMPOSE ps -q piston)"
install_pkg() {
  docker exec "$PISTON_CID" sh -c \
    "curl -s -X POST http://localhost:2000/api/v2/packages -H 'Content-Type: application/json' -d '{\"language\":\"$1\",\"version\":\"$2\"}'" \
    >/dev/null || true
}
install_pkg python 3.10.0
install_pkg java 15.0.2
install_pkg gcc 10.2.0

echo "==> Done. Services:"
$COMPOSE ps
echo
echo "App:  https://\${APP_DOMAIN}   API: https://\${API_DOMAIN}"
echo "(DB tables are created from the models automatically on API startup.)"
