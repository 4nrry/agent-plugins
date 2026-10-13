#!/usr/bin/env bash
# Grava a secao de video do Grok Build sob ZDR apontando para um bucket S3-compativel
# seu (R2, S3, MinIO). Pede as chaves sem eco; nada vai para o historico.
#
#   S3_ENDPOINT=https://<conta>.r2.cloudflarestorage.com S3_BUCKET=grok-videos grok-zdr-bucket.sh
#
# Opcional: S3_REGION (padrao auto), ou S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY no ambiente.
set -euo pipefail
endpoint="${S3_ENDPOINT:?defina S3_ENDPOINT}"
bucket="${S3_BUCKET:?defina S3_BUCKET}"
region="${S3_REGION:-auto}"
config="$HOME/.grok/managed_config.toml"
section="[tools.zdr_video_output_s3]"

key_id="${S3_ACCESS_KEY_ID:-}"
secret="${S3_SECRET_ACCESS_KEY:-}"
[ -n "$key_id" ] || read -rp "Access Key ID: " key_id
[ -n "$secret" ] || { read -rsp "Secret Access Key: " secret; echo; }
[ -n "$key_id" ] && [ -n "$secret" ] || { echo "faltou a chave" >&2; exit 1; }

mkdir -p "$(dirname "$config")"
touch "$config"
chmod 600 "$config"
if grep -qF "$section" "$config"; then
  echo "ja existe $section em $config; edite a mao ou apague a secao antes" >&2
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
echo "Reinicie o Grok Build para valer."
