#!/usr/bin/env bash
# Daily cron script: pull the latest NASS Agricultural Prices indexes and restart
# the app only when the data changed. Safe to run every day — the fetch is a few
# seconds, so polling daily picks up a late or rescheduled release the next morning.
#
# Runs relative to the repo checkout it lives in and logs to ~/logs (no crontab
# redirect needed — never redirect into /var/log from a user crontab). Example:
#   0 5 * * * /path/to/repo/refresh_data.sh
#
# Defaults assume Podman (aliased as docker), which requires the fully qualified
# localhost/ image name and --pull=never for local-only images.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${AG_PRICES_IMAGE:-localhost/ag-prices-viz:latest}"
DATA_DIR="$REPO_DIR/data"
PARQUET="$DATA_DIR/ag_prices.parquet"

LOG_DIR="${REFRESH_LOG_DIR:-$HOME/logs}"
mkdir -p "$LOG_DIR" "$DATA_DIR"
exec > >(tee -a "$LOG_DIR/ag-prices-viz-refresh.log") 2>&1

# One run at a time — a manual run during the cron window must not collide
exec 9>"$DATA_DIR/.refresh.lock"
if ! flock -n 9; then
    echo "[$(date -Iseconds)] Another refresh is already running, exiting"
    exit 0
fi

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

echo "[$(date -Iseconds)] Checking for new agricultural prices data"
BEFORE=""
[[ -f "$PARQUET" ]] && BEFORE="$(sha256 "$PARQUET")"

# API key (from .env) is only needed for the fetch step
docker run --rm --pull=never \
    --env-file "$REPO_DIR/.env" \
    -v "$DATA_DIR:/app/data:rw" \
    "$IMAGE" \
    python fetch_data.py

if [[ "$BEFORE" == "$(sha256 "$PARQUET")" ]]; then
    echo "[$(date -Iseconds)] No new data, nothing to do"
    exit 0
fi

echo "[$(date -Iseconds)] New data detected, restarting app"
# Requires passwordless sudo for this one command (see OPERATIONS.md)
sudo systemctl restart ag-prices-viz
