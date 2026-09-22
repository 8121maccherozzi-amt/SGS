#!/usr/bin/env bash
# Avvio di SGS Live su Linux e macOS. Al primo utilizzo prepara tutto da solo.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Prima installazione: preparo il programma, può richiedere qualche minuto."
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

exec ./.venv/bin/python sgs.py "${@:-avvia}"
