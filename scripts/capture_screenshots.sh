#!/usr/bin/env bash
set -e

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE_URL="file://$(pwd)/zendesk-app/assets/index.html"
OUT_DIR="docs/screenshots"
USER_DIR="/tmp/chrome-screenshot-profile"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR/test.png"

screens=(
  "01-ai-ticket-summary.png:?tab=summary&action=1&sub=formatted:480,950"
  "02-ai-troubleshooting.png:?tab=troubleshoot&action=1:480,820"
  "03-ai-reply-drafting.png:?tab=reply&action=1:480,820"
  "04-ticket-classification-triage.png:?tab=triage&action=1:480,820"
  "05-sentiment-frustration-radar.png:?tab=radar&action=1:480,820"
  "06-engineering-escalation.png:?tab=escalation&action=1:480,820"
  "07-shift-handover.png:?tab=handover&action=1:480,820"
  "08-knowledge-base-recommendations.png:?tab=knowledge&action=1:480,820"
  "09-similar-ticket-discovery.png:?tab=similar&action=1:480,820"
)

for item in "${screens[@]}"; do
  IFS=":" read -r filename query win_size <<< "$item"
  echo "Capturing $filename ($win_size)..."
  "$CHROME" \
    --headless=new \
    --no-sandbox \
    --disable-gpu \
    --disable-crash-reporter \
    --crash-dumps-dir=/tmp \
    --user-data-dir="$USER_DIR" \
    --virtual-time-budget=2000 \
    --window-size="$win_size" \
    --screenshot="$OUT_DIR/$filename" \
    "$BASE_URL$query" 2>/dev/null || true
done

echo "✅ All screenshots generated in $OUT_DIR"
ls -lh "$OUT_DIR"
