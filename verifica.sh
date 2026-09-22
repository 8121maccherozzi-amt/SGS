#!/usr/bin/env bash
# Verifica se questo computer ha già tutto il necessario per SGS Live.
# Non installa nulla e non modifica nulla.
echo
echo "=========================================================="
echo "  SGS Live — verifica dei requisiti (nessuna modifica)"
echo "=========================================================="
echo

trovato=""
for candidato in python3 python; do
  if command -v "$candidato" >/dev/null 2>&1; then trovato="$candidato"; break; fi
done

if [ -z "$trovato" ]; then
  echo "[--] Python non risulta installato."
  echo "     macOS: si installa da https://www.python.org/downloads/macos/"
  echo "     Linux: chiedere l'installazione del pacchetto python3 e python3-venv."
  exit 1
fi

echo "[OK] Python risulta già installato."
echo "     Comando:  $trovato"
echo "     Versione: $("$trovato" --version 2>&1)"
echo "     Percorso: $("$trovato" -c 'import sys;print(sys.executable)')"
echo

if ! "$trovato" -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)'; then
  echo "[!!] Versione troppo vecchia: serve Python 3.10 o superiore."
  exit 1
fi
echo "[OK] La versione è sufficiente (serve 3.10 o superiore)."

"$trovato" -m venv --help >/dev/null 2>&1 \
  && echo "[OK] Il componente per creare l'ambiente di lavoro è presente." \
  || { echo "[!!] Manca il componente «venv» (su Debian/Ubuntu: pacchetto python3-venv)."; exit 1; }

"$trovato" -m pip --version >/dev/null 2>&1 \
  && echo "[OK] Il gestore dei componenti aggiuntivi (pip) è presente." \
  || { echo "[!!] Manca «pip»."; exit 1; }

echo
echo "----------------------------------------------------------"
echo "  ESITO: questo computer è pronto. Avvia con ./avvia.sh"
echo "----------------------------------------------------------"
