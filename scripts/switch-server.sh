#!/usr/bin/env bash
# Start (or stop) a private Switch server with Mattermost, without Switch Console.
#
# This is the stack the end-to-end test runs against. It uses Switch's own
# published compose file and images, on ports that do not clash with the
# server Switch Console runs (API 18000, Mattermost 18065, Gateway 13000).
#
#   scripts/switch-server.sh up      # first run pulls a few GB
#   scripts/switch-server.sh down    # stop, keep data
#   scripts/switch-server.sh reset   # stop and delete data
set -euo pipefail

SWITCH_VERSION="${SWITCH_VERSION:-0.31.0}"
SWITCH_REF="${SWITCH_REF:-eba577e}"   # commit of sandbox-quantum/switch the compose file is taken from
DIR="$(cd "$(dirname "$0")/.." && pwd)/.proveit/switch-server"
PROJECT=proveit-switch
RAW="https://raw.githubusercontent.com/sandbox-quantum/switch/${SWITCH_REF}"

mkdir -p "$DIR"
cd "$DIR"

compose() { docker compose -p "$PROJECT" -f compose.yml --env-file .env --profile collab --profile gateway "$@"; }

case "${1:-up}" in
  up)
    if [ ! -f compose.yml ]; then
      curl -fsSL "$RAW/deploy/local/standalone-docker-compose.yml" -o compose.yml
    fi
    if [ ! -f .env ]; then
      curl -fsSL "$RAW/.env.example" -o .env
      curl -fsSL "$RAW/deploy/local/generate-env-secrets.sh" -o generate-env-secrets.sh
      bash generate-env-secrets.sh .env proveit
      sed -i.bak \
        -e "s/^SWITCH_VERSION=.*/SWITCH_VERSION=${SWITCH_VERSION}/" \
        -e "s/^API_HOST_PORT=.*/API_HOST_PORT=18000/" \
        -e "s/^MATTERMOST_HOST_PORT=.*/MATTERMOST_HOST_PORT=18065/" \
        -e "s/^GATEWAY_HOST_PORT=.*/GATEWAY_HOST_PORT=13000/" \
        -e "s/^POSTGRES_HOST_PORT=.*/POSTGRES_HOST_PORT=15432/" .env
      rm -f .env.bak
    fi
    compose up -d
    echo "Waiting for Switch on http://127.0.0.1:18000 ..."
    for _ in $(seq 1 90); do
      if curl -fs http://127.0.0.1:18000/health >/dev/null 2>&1; then break; fi
      sleep 2
    done
    curl -fs http://127.0.0.1:18000/health && echo
    echo "Mattermost: http://127.0.0.1:18065  (user: $(grep ^MATTERMOST_USER= .env | cut -d= -f2), password in $DIR/.env)"
    echo "Settings file for the Intake agent: $DIR/.env"
    ;;
  down) compose down ;;
  reset) compose down -v ;;
  *) echo "usage: $0 up|down|reset" >&2; exit 2 ;;
esac
