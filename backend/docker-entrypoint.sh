#!/usr/bin/env sh
set -e

# Apply database migrations (safe/no-op if already at head). For SQLite dev this
# also creates the schema. Skip with RUN_MIGRATIONS=0.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] applying database migrations..."
  alembic upgrade head || {
    echo "[entrypoint] migration failed" >&2
    exit 1
  }
fi

echo "[entrypoint] starting: $*"
exec "$@"
