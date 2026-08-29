#!/usr/bin/env bash
# Install the language runtimes we need into a running Piston container.
# Run once after `docker compose -f piston/docker-compose.yml up -d`.
set -e
PISTON=${PISTON_URL:-http://localhost:2000}

install() {
  echo "Installing $1 $2 ..."
  curl -s -X POST "$PISTON/api/v2/packages" \
    -H 'Content-Type: application/json' \
    -d "{\"language\":\"$1\",\"version\":\"$2\"}" | head -c 300
  echo
}

# Versions Piston publishes; adjust if a version is unavailable in your index.
install python 3.10.0
install java 15.0.2
install c++ 10.2.0

echo "Done. Installed runtimes:"
curl -s "$PISTON/api/v2/runtimes"
