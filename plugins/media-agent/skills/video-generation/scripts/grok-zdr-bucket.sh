#!/usr/bin/env bash
# Write Grok Build's ZDR video-output section, pointing to your own S3-compatible
# bucket (R2, S3, MinIO). Prompts for the keys without echo; nothing reaches shell history.
#
#   S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com S3_BUCKET=grok-videos grok-zdr-bucket.sh
#
# Optional: S3_REGION (default auto), or S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY in the environment.
set -euo pipefail
endpoint="${S3_ENDPOINT:?set S3_ENDPOINT}"
bucket="${S3_BUCKET:?set S3_BUCKET}"
region="${S3_REGION:-auto}"
config="$HOME/.grok/managed_config.toml"
section="[tools.zdr_video_output_s3]"

key_id="${S3_ACCESS_KEY_ID:-}"
secret="${S3_SECRET_ACCESS_KEY:-}"
[ -n "$key_id" ] || read -rp "Access Key ID: " key_id
[ -n "$secret" ] || { read -rsp "Secret Access Key: " secret; echo; }
[ -n "$key_id" ] && [ -n "$secret" ] || { echo "missing key" >&2; exit 1; }

mkdir -p "$(dirname "$config")"
touch "$config"
chmod 600 "$config"
if grep -qF "$section" "$config"; then
  echo "$section already exists in $config; edit it by hand or delete the section first" >&2
  exit 1
fi

umask 077
{
  echo
  echo "$section"
  echo "bucket = \"$bucket\""
  echo "endpoint = \"$endpoint\""
  echo "region = \"$region\""
  echo "key_prefix = \"grok-videos/\""
  echo
  echo "[tools.zdr_video_output_s3.read_write]"
  echo "access_key_id = \"$key_id\""
  echo "secret_access_key = \"$secret\""
  echo
  echo "[tools.zdr_video_output_s3.read_only]"
  echo "access_key_id = \"$key_id\""
  echo "secret_access_key = \"$secret\""
} >> "$config"
unset key_id secret
python3 -c "import sys,tomllib; s=tomllib.load(open(sys.argv[1],'rb'))['tools']['zdr_video_output_s3']; print('ok:', s['bucket'])" "$config"
echo "Restart Grok Build for this to take effect."
