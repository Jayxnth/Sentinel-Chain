#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: deploy.sh [options]

Required:
  --database-url <url>         SQLAlchemy async URL (postgresql+asyncpg://...)
  --api-key <key>              API key expected by backend auth

Optional:
  --app-dir <path>             App location on VM (default: /opt/sentinel-chain)
  --venv-path <path>           Venv location (default: <app-dir>/.venv)
  --google-api-key <key>       Gemini API key (recommended)
  --gemini-model <model>       Gemini model (default: gemini-2.5-flash)
  --service-name <name>        Systemd service name (default: sentinel-api)
  --service-user <user>        Linux user for service (default: sentinel)
  --env-file <path>            Env file path (default: /etc/sentinel-chain/sentinel-api.env)
  --host <host>                Uvicorn host (default: 0.0.0.0)
  --port <port>                Uvicorn port (default: 8000)
  --help                       Show this help text
USAGE
}

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "This script must run as root (use sudo)." >&2
  exit 1
fi

APP_DIR="/opt/sentinel-chain"
VENV_PATH=""
DATABASE_URL=""
API_KEY=""
GOOGLE_API_KEY=""
GEMINI_MODEL="gemini-2.5-flash"
SERVICE_NAME="sentinel-api"
SERVICE_USER="sentinel"
SERVICE_GROUP=""
ENV_FILE="/etc/sentinel-chain/sentinel-api.env"
APP_HOST="0.0.0.0"
APP_PORT="8000"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    --venv-path)
      VENV_PATH="$2"
      shift 2
      ;;
    --database-url)
      DATABASE_URL="$2"
      shift 2
      ;;
    --api-key)
      API_KEY="$2"
      shift 2
      ;;
    --google-api-key)
      GOOGLE_API_KEY="$2"
      shift 2
      ;;
    --gemini-model)
      GEMINI_MODEL="$2"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --service-user)
      SERVICE_USER="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --host)
      APP_HOST="$2"
      shift 2
      ;;
    --port)
      APP_PORT="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$VENV_PATH" ]]; then
  VENV_PATH="$APP_DIR/.venv"
fi

if [[ -z "$DATABASE_URL" ]]; then
  echo "--database-url is required." >&2
  exit 1
fi
if [[ -z "$API_KEY" ]]; then
  echo "--api-key is required." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/requirements.txt" ]]; then
  echo "requirements.txt not found in $APP_DIR" >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/fast-api-deploy/sentinel-api.service.template" ]]; then
  echo "Service template not found: $APP_DIR/fast-api-deploy/sentinel-api.service.template" >&2
  exit 1
fi

if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --user-group --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

mkdir -p "$APP_DIR"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$APP_DIR"

python3 -m venv "$VENV_PATH"
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$APP_DIR/requirements.txt"

env_dir="$(dirname "$ENV_FILE")"
install -d -m 750 "$env_dir"
install -m 600 /dev/null "$ENV_FILE"
chown root:"$SERVICE_GROUP" "$ENV_FILE"
chmod 640 "$ENV_FILE"

sq() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\"'\"'/g")"
}

{
  printf "API_KEY=%s\n" "$(sq "$API_KEY")"
  printf "DATABASE_URL=%s\n" "$(sq "$DATABASE_URL")"
  printf "GOOGLE_API_KEY=%s\n" "$(sq "$GOOGLE_API_KEY")"
  printf "GEMINI_MODEL=%s\n" "$(sq "$GEMINI_MODEL")"
  printf "PYTHONUNBUFFERED='1'\n"
} >"$ENV_FILE"

chown root:"$SERVICE_GROUP" "$ENV_FILE"
chmod 640 "$ENV_FILE"

cd "$APP_DIR"
DATABASE_URL="$DATABASE_URL" "$VENV_PATH/bin/python" -c "import asyncio; from backend.db.database import init_db; asyncio.run(init_db())"

service_template="$APP_DIR/fast-api-deploy/sentinel-api.service.template"
service_target="/etc/systemd/system/${SERVICE_NAME}.service"

esc() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

app_dir_esc="$(esc "$APP_DIR")"
venv_path_esc="$(esc "$VENV_PATH")"
service_user_esc="$(esc "$SERVICE_USER")"
service_group_esc="$(esc "$SERVICE_GROUP")"
env_file_esc="$(esc "$ENV_FILE")"
app_host_esc="$(esc "$APP_HOST")"
app_port_esc="$(esc "$APP_PORT")"

sed \
  -e "s/__APP_DIR__/${app_dir_esc}/g" \
  -e "s/__VENV_PATH__/${venv_path_esc}/g" \
  -e "s/__SERVICE_USER__/${service_user_esc}/g" \
  -e "s/__SERVICE_GROUP__/${service_group_esc}/g" \
  -e "s/__ENV_FILE__/${env_file_esc}/g" \
  -e "s/__APP_HOST__/${app_host_esc}/g" \
  -e "s/__APP_PORT__/${app_port_esc}/g" \
  "$service_template" >"$service_target"

chmod 644 "$service_target"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
