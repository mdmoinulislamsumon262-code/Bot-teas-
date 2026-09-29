#!/usr/bin/env bash
set -euo pipefail

: "${BOT_TOKEN:?Set BOT_TOKEN in Render Environment before starting the bot}"
: "${ADMIN_ID:?Set ADMIN_ID in Render Environment before starting the bot}"

exec python main.py