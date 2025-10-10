#!/bin/bash
set -euo pipefail

CONF_FILE="$PGDATA/postgresql.conf"

if [ ! -f "$CONF_FILE" ]; then
  echo "PostgreSQL configuration file not found at $CONF_FILE" >&2
  exit 1
fi

cat >> "$CONF_FILE" <<'EOC'
# Custom settings for zoo tracker development
max_connections = 200
shared_buffers = 1GB
effective_cache_size = 3GB
maintenance_work_mem = 256MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 5041kB
huge_pages = off
min_wal_size = 1GB
max_wal_size = 4GB
EOC
