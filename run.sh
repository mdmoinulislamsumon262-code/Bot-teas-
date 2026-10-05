#!/usr/bin/env bash
set -euo pipefail

: "${BOT_TOKEN:?Set BOT_TOKEN in the Railway service variables before starting the bot}"
: "${ADMIN_ID:?Set ADMIN_ID (numeric Telegram user ID) in Railway service variables}"

if [[ ! "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
  echo "ADMIN_ID must contain only digits." >&2
  exit 1
fi

# Railway sets this automatically when a Volume is mounted. Keep DATA_DIR
# inside that mount; an unrelated override points at the disposable container
# filesystem and makes data appear to vanish after restarts.
if [[ -n "${RAILWAY_VOLUME_MOUNT_PATH:-}" ]]; then
  volume_path="${RAILWAY_VOLUME_MOUNT_PATH%/}"
  [[ -n "$volume_path" ]] || volume_path="/"
  data_dir="${DATA_DIR:-$volume_path}"
  case "$data_dir" in
    "$volume_path"|"$volume_path"/*) ;;
    *)
      echo "WARNING: DATA_DIR=$data_dir is outside Railway volume $volume_path; using the volume mount." >&2
      data_dir="$volume_path"
      ;;
  esac
  export DATA_DIR="$data_dir"
else
  export DATA_DIR="${DATA_DIR:-/app/data}"
  echo "WARNING: RAILWAY_VOLUME_MOUNT_PATH is unset; $DATA_DIR is not guaranteed to persist across restarts." >&2
fi
exec python main.py
