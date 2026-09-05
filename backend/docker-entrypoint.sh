#!/usr/bin/env sh
set -e

# The schema is created from the SQLAlchemy models on app startup (see
# app/lifespan.py) — the app is pre-launch, so there are no migrations to run.
# When the schema later needs versioned, incremental changes against live data,
# introduce a migration tool (e.g. Alembic) and run it here.

echo "[entrypoint] starting: $*"
exec "$@"
