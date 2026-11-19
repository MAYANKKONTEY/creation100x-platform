#!/usr/bin/env bash
# Copy ClipBox sessions from the UNO Q to this computer over Wi-Fi (SSH).
#
# Usage: tools/pull_sessions.sh arduino@<board-name>.local [destination]
#   or:  CLIPBOX_BOARD=arduino@<board-name>.local tools/pull_sessions.sh
#
# The board name is the one you chose when setting up the UNO Q in App Lab.
# Sessions already copied are skipped (rsync) or overwritten (scp fallback).
set -euo pipefail

BOARD="${1:-${CLIPBOX_BOARD:-}}"
DEST="${2:-./sessions}"
REMOTE_DIR="${CLIPBOX_REMOTE_DIR:-/home/arduino/ArduinoApps/clipbox/sessions}"

if [[ -z "$BOARD" ]]; then
  echo "Usage: $0 arduino@<board-name>.local [destination]" >&2
  exit 1
fi

mkdir -p "$DEST"
echo "Copying $BOARD:$REMOTE_DIR/ -> $DEST/"

if command -v rsync >/dev/null 2>&1 && ssh "$BOARD" 'command -v rsync' >/dev/null 2>&1; then
  rsync -avh --progress --exclude '*.tmp' "$BOARD:$REMOTE_DIR/" "$DEST/"
else
  echo "(rsync not available on both sides, using scp)"
  scp -r "$BOARD:$REMOTE_DIR/." "$DEST/"
fi

echo "Done. Sessions:"
ls -1 "$DEST"
