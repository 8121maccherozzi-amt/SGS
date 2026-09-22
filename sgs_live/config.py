"""Configurazione di SGS Live (letta da variabili d'ambiente o da .env)."""
from __future__ import annotations

import os
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent


def _carica_dotenv() -> None:
    env = RADICE / ".env"
    if not env.exists():
        return
    for riga in env.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, valore = riga.split("=", 1)
        os.environ.setdefault(chiave.strip(), valore.strip())


_carica_dotenv()

MODELLO = os.environ.get("SGS_MODELLO", "claude-opus-5")
CARTELLA_DOCUMENTI = Path(os.environ.get("SGS_DOCUMENTI", RADICE / "documenti")).resolve()
PERCORSO_DB = Path(os.environ.get("SGS_DB", RADICE / "sgs_live.db")).resolve()
PORTA = int(os.environ.get("SGS_PORTA", "8770"))
CARTELLA_WEB = RADICE / "web"

# Sistemi TGV presidiati (prefissi usati nella naming convention documentale).
SISTEMI = ["TGV", "MET", "FGC", "FPG", "FIL"]

TIPI_DOCUMENTO = [
    "Politica della Sicurezza",
    "Manuale",
    "Procedura",
    "Istruzione Operativa",
    "Norma di Esercizio",
    "Ordine di Servizio",
    "Registro",
    "Modulo",
    "Altro",
]
