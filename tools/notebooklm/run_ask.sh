#!/usr/bin/env bash
# Interroga un notebook NotebookLM: la risposta e' generata dall'AI di
# NotebookLM ed e' ancorata alle SOLE fonti caricate in quel notebook, con
# citazioni inline [1], [2].
#
# Uso, dalla radice del repo:
#   bash tools/notebooklm/run_ask.sh --list
#   bash tools/notebooklm/run_ask.sh -n "Normativa" "quali sono i requisiti per un SGS?"
#   bash tools/notebooklm/run_ask.sh -n abc123 --json "domanda"
#
# Opzioni:
#   --list              elenca i notebook (con ID e titolo) e termina
#   -n, --notebook X    ID (anche parziale) o porzione di titolo del notebook
#   -f, --cookie FILE   file cookie (default: cookie.txt nella radice del repo)
#   -h, --help          questo messaggio
# Qualunque altra opzione viene inoltrata a `notebooklm ask` (es. --json,
# --new, --save-as-note, -s <source_id>, --timeout N).
#
# I cookie sono presi, in ordine, dal file indicato e poi dalla variabile
# d'ambiente NOTEBOOKLM_AUTH_JSON, esattamente come in run_export.sh.
#
# ATTENZIONE: il payload di autenticazione equivale all'accesso all'intero
# account Google. Non committarlo. Il cookie __Secure-1PSIDTS ruota ogni
# pochi minuti: usa sempre una copia fresca.
set -uo pipefail

COOKIE_FILE="cookie.txt"
NOTEBOOK=""
DO_LIST=0
PASSTHRU=()
QUESTION=""

while [ $# -gt 0 ]; do
    case "$1" in
        --list) DO_LIST=1; shift ;;
        -n|--notebook) NOTEBOOK="${2:-}"; shift 2 ;;
        -f|--cookie) COOKIE_FILE="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
        -*) PASSTHRU+=("$1"); shift ;;
        *) QUESTION="$1"; shift ;;
    esac
done

# --- 1. Cookie -------------------------------------------------------------
AUTH_FILE="$(mktemp)"
trap 'rm -f "${AUTH_FILE}"' EXIT

if [ -f "${COOKIE_FILE}" ]; then
    python3 tools/notebooklm/cookie_to_auth.py -i "${COOKIE_FILE}" > "${AUTH_FILE}" || exit 1
elif [ -n "${NOTEBOOKLM_AUTH_JSON:-}" ]; then
    python3 tools/notebooklm/cookie_to_auth.py --from-env > "${AUTH_FILE}" || exit 1
else
    echo "ERRORE: nessuna fonte di cookie. Crea ${COOKIE_FILE} oppure imposta NOTEBOOKLM_AUTH_JSON." >&2
    exit 1
fi
chmod 600 "${AUTH_FILE}"
NOTEBOOKLM_AUTH_JSON="$(cat "${AUTH_FILE}")"
export NOTEBOOKLM_AUTH_JSON

# --- 2. Elenco notebook ----------------------------------------------------
if [ "${DO_LIST}" -eq 1 ]; then
    exec timeout 120 notebooklm list --no-truncate
fi

if [ -z "${QUESTION}" ]; then
    echo "ERRORE: manca la domanda. Esempio:" >&2
    echo "  bash tools/notebooklm/run_ask.sh -n \"Normativa\" \"quali sono i requisiti per un SGS?\"" >&2
    exit 1
fi

# --- 3. Risoluzione del notebook (ID parziale o titolo) --------------------
NB_ARGS=()
if [ -n "${NOTEBOOK}" ]; then
    RESOLVED="$(timeout 120 notebooklm list --json 2>/dev/null | NB_QUERY="${NOTEBOOK}" python3 -c '
import json, os, sys

query = os.environ["NB_QUERY"].strip().lower()
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(2)                      # elenco non leggibile: si passa il valore grezzo alla CLI

# Tollera sia una lista sia un dict che la incapsula (chiave notebooks/items/data).
if isinstance(data, dict):
    for key in ("notebooks", "items", "data", "results"):
        if isinstance(data.get(key), list):
            data = data[key]
            break
if not isinstance(data, list):
    sys.exit(2)

def field(nb, *names):
    for n in names:
        val = nb.get(n)
        if isinstance(val, str) and val:
            return val
    return ""

exact, partial = [], []
for nb in data:
    if not isinstance(nb, dict):
        continue
    nb_id = field(nb, "id", "notebook_id", "notebookId")
    title = field(nb, "title", "name", "emoji_title")
    if not nb_id:
        continue
    if query == nb_id.lower() or query == title.lower():
        exact.append((nb_id, title))
    elif nb_id.lower().startswith(query) or query in title.lower():
        partial.append((nb_id, title))

hits = exact or partial
if len(hits) == 1:
    print(hits[0][0])
    print(hits[0][1], file=sys.stderr)
    sys.exit(0)
if not hits:
    print(f"Nessun notebook corrisponde a: {query}", file=sys.stderr)
    sys.exit(1)
print("Piu di un notebook corrisponde. Usa l ID esatto:", file=sys.stderr)
for nb_id, title in hits:
    print(f"  {nb_id}  {title}", file=sys.stderr)
sys.exit(1)
')"
    RC=$?
    if [ "${RC}" -eq 0 ] && [ -n "${RESOLVED}" ]; then
        NB_ARGS=(-n "${RESOLVED}")
    elif [ "${RC}" -eq 1 ]; then
        exit 1
    else
        # elenco non interpretabile: si lascia risolvere alla CLI (ID parziale)
        NB_ARGS=(-n "${NOTEBOOK}")
    fi
fi

# --- 4. Domanda ------------------------------------------------------------
timeout 600 notebooklm ask "${NB_ARGS[@]}" "${PASSTHRU[@]}" "${QUESTION}"
