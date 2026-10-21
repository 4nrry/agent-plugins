#!/usr/bin/env bash
# Start ComfyUI headless, on loopback only, with the diffusion model cast to fp8 at
# load (--fp8_e4m3fn-unet) so a 12 GB bf16 model fits an 8 GB GPU. COMFY_HOME is the
# directory holding ComfyUI/ (the clone) and .venv/ (the venv with torch);
# COMFY_PORT changes the port (default 8188).
set -euo pipefail
home="${COMFY_HOME:-}"
[ -n "$home" ] || { echo "comfy-serve: set COMFY_HOME (directory with ComfyUI/ and .venv/)" >&2; exit 2; }
[ -x "$home/.venv/bin/python" ] || { echo "comfy-serve: $home/.venv/bin/python does not exist" >&2; exit 2; }
[ -f "$home/ComfyUI/main.py" ] || { echo "comfy-serve: $home/ComfyUI/main.py does not exist" >&2; exit 2; }
exec "$home/.venv/bin/python" "$home/ComfyUI/main.py" \
  --listen 127.0.0.1 --port "${COMFY_PORT:-8188}" \
  --disable-auto-launch --dont-print-server \
  --fp8_e4m3fn-unet "$@"
