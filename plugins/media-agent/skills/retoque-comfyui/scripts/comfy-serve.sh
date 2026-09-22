#!/usr/bin/env bash
# Sobe o ComfyUI sem interface, so na loopback, com o modelo de difusao convertido
# para fp8 ao carregar (--fp8_e4m3fn-unet): e o que faz um modelo bf16 de 12 GB
# caber numa GPU de 8 GB. COMFY_HOME aponta para o diretorio que contem ComfyUI/
# (o clone) e .venv/ (o venv com torch); COMFY_PORT muda a porta (padrao 8188).
set -euo pipefail
home="${COMFY_HOME:-}"
[ -n "$home" ] || { echo "comfy-serve: defina COMFY_HOME (diretorio com ComfyUI/ e .venv/)" >&2; exit 2; }
[ -x "$home/.venv/bin/python" ] || { echo "comfy-serve: $home/.venv/bin/python nao existe" >&2; exit 2; }
[ -f "$home/ComfyUI/main.py" ] || { echo "comfy-serve: $home/ComfyUI/main.py nao existe" >&2; exit 2; }
exec "$home/.venv/bin/python" "$home/ComfyUI/main.py" \
  --listen 127.0.0.1 --port "${COMFY_PORT:-8188}" \
  --disable-auto-launch --dont-print-server \
  --fp8_e4m3fn-unet "$@"
