#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: describe_image.sh <image-path> [prompt]

Environment overrides:
  MODEL       Vision model name (default: qwen3627b_code)
  ENDPOINT    OpenAI-compatible chat completions endpoint
  AUTH_TOKEN  Bearer token (default: sk-no-key)
  MAX_TIME    curl timeout in seconds (default: 120)
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: required command not found: $1" >&2
    exit 127
  fi
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 64
fi

IMAGE=$1
PROMPT=${2:-"Describe this image in detail."}
MODEL=${MODEL:-qwen3627b_code}
ENDPOINT=${ENDPOINT:-http://makkalot.local:8001/v1/chat/completions}
AUTH_TOKEN=${AUTH_TOKEN:-sk-no-key}
MAX_TIME=${MAX_TIME:-120}

if [[ ! -f "$IMAGE" ]]; then
  echo "Error: image file does not exist: $IMAGE" >&2
  exit 66
fi

if [[ ! -r "$IMAGE" ]]; then
  echo "Error: image file is not readable: $IMAGE" >&2
  exit 66
fi

require_cmd base64
require_cmd curl
require_cmd python3

case "${IMAGE##*.}" in
  jpg|JPG|jpeg|JPEG)
    MIME_TYPE=image/jpeg
    ;;
  png|PNG)
    MIME_TYPE=image/png
    ;;
  webp|WEBP)
    MIME_TYPE=image/webp
    ;;
  gif|GIF)
    MIME_TYPE=image/gif
    ;;
  *)
    MIME_TYPE=image/jpeg
    ;;
esac

payload=$(mktemp "${TMPDIR:-/tmp}/localimg_payload.XXXXXX.json")
response=$(mktemp "${TMPDIR:-/tmp}/localimg_response.XXXXXX.json")
b64_file=$(mktemp "${TMPDIR:-/tmp}/localimg_b64.XXXXXX.txt")
cleanup() {
  rm -f "$payload" "$response" "$b64_file"
}
trap cleanup EXIT

if ! base64 -i "$IMAGE" >"$b64_file" 2>/dev/null; then
  base64 "$IMAGE" >"$b64_file"
fi

python3 - "$MODEL" "$PROMPT" "$MIME_TYPE" "$b64_file" >"$payload" <<'PY'
import json
import sys

model, prompt, mime_type, b64_path = sys.argv[1:]
with open(b64_path, "r", encoding="utf-8") as f:
    b64 = "".join(f.read().split())

payload = {
    "model": model,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
            ],
        }
    ],
}
json.dump(payload, sys.stdout)
PY

curl -sS --max-time "$MAX_TIME" "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -d @"$payload" >"$response"

python3 - "$response" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

try:
    print(data["choices"][0]["message"]["content"])
except (KeyError, IndexError, TypeError) as exc:
    raise SystemExit(f"Error: unexpected response shape: {json.dumps(data, ensure_ascii=False)}") from exc
PY
