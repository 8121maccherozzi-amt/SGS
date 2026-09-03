#!/usr/bin/env bash
# Flusso completo di export NotebookLM, da lanciare dalla radice del repo:
#   1) converte la riga 'Cookie:' nel formato atteso da notebooklm-py
#   2) verifica l'autenticazione
#   3) elenca i notebook ed esporta fonti e note
#
# Uso:  bash tools/notebooklm/run_export.sh [file_cookie] [cartella_output]
# Default: cookie.txt e ./notebooklm_export (entrambi esclusi da git)
#
# ATTENZIONE: il file cookie contiene credenziali equivalenti all'accesso
# all'intero account Google. Non committarlo. Dopo l'export, valuta di
# revocare la sessione da Account Google -> Sicurezza -> I tuoi dispositivi.
set -uo pipefail

COOKIE_FILE="${1:-cookie.txt}"
OUT_DIR="${2:-notebooklm_export}"
AUTH_FILE="$(mktemp)"
trap 'rm -f "${AUTH_FILE}"' EXIT

if [ ! -f "${COOKIE_FILE}" ]; then
    echo "ERRORE: file cookie non trovato: ${COOKIE_FILE}" >&2
    exit 1
fi

echo "=== 1. Conversione cookie ==="
python3 tools/notebooklm/cookie_to_auth.py -i "${COOKIE_FILE}" > "${AUTH_FILE}" || exit 1
chmod 600 "${AUTH_FILE}"

NOTEBOOKLM_AUTH_JSON="$(cat "${AUTH_FILE}")"
export NOTEBOOKLM_AUTH_JSON

echo
echo "=== 2. Verifica autenticazione ==="
timeout 120 notebooklm auth check --test --json 2>&1 | tail -20
echo "(exit: ${PIPESTATUS[0]})"

echo
echo "=== 3. Elenco ed export notebook ==="
mkdir -p "${OUT_DIR}"
timeout 900 python3 tools/notebooklm/connector.py --output "${OUT_DIR}" 2>&1 | tail -60
echo "(exit: ${PIPESTATUS[0]})"
