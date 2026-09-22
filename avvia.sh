#!/usr/bin/env bash
# Avvio di SGS Live (crea l'ambiente virtuale al primo utilizzo).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Creato .env: inserire ANTHROPIC_API_KEY prima di usare l'assistente."
fi
exec ./.venv/bin/python sgs.py "${1:-avvia}"
