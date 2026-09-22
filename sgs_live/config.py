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

import json


def _booleano(nome: str, predefinito: str = "0") -> bool:
    return os.environ.get(nome, predefinito).strip().lower() in {"1", "true", "si", "sì", "yes", "on"}


def _elenco(valore: str) -> list[str]:
    """Separatore «;»: compatibile con i percorsi Windows (C:\..., \\server\condivisione)."""
    return [v.strip() for v in valore.split(";") if v.strip()]


MODELLO = os.environ.get("SGS_MODELLO", "claude-opus-5")

# Una o più cartelle sorgente, separate da «;». Possono essere percorsi di rete
# (\\server\SGS) o punti di mount; vengono lette senza mai essere modificate.
CARTELLE_DOCUMENTI: list[Path] = [
    Path(os.path.expandvars(os.path.expanduser(c))).resolve()
    for c in _elenco(os.environ.get("SGS_DOCUMENTI", "") or str(RADICE / "documenti"))
]
# Cartella in cui atterrano i file caricati dalla dashboard (mai una cartella sorgente
# in sola lettura). Per compatibilità resta esposta come CARTELLA_DOCUMENTI.
CARTELLA_DOCUMENTI = Path(
    os.environ.get("SGS_CARTELLA_CARICAMENTI", "") or CARTELLE_DOCUMENTI[0]).resolve()

# Le cartelle possono essere cambiate dalla dashboard: la scelta vive qui e ha
# la precedenza su SGS_DOCUMENTI, così non serve toccare il file .env.
PERCORSO_IMPOSTAZIONI = RADICE / "impostazioni.json"


def _normalizza(percorso: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(percorso.strip().strip('"').strip("'")))).resolve()


def cartelle_documenti() -> list[Path]:
    """Cartelle sorgente attuali: quelle scelte dalla dashboard, altrimenti quelle di .env."""
    try:
        salvate = json.loads(PERCORSO_IMPOSTAZIONI.read_text(encoding="utf-8")).get("cartelle")
        if salvate:
            return [_normalizza(c) for c in salvate]
    except (FileNotFoundError, ValueError, OSError):
        pass
    return list(CARTELLE_DOCUMENTI)


def salva_cartelle(cartelle: list[str]) -> list[Path]:
    puliti = [c.strip() for c in cartelle if c and c.strip()]
    if not puliti:
        raise ValueError("Indicare almeno una cartella.")
    PERCORSO_IMPOSTAZIONI.write_text(
        json.dumps({"cartelle": puliti}, ensure_ascii=False, indent=1), encoding="utf-8")
    return [_normalizza(c) for c in puliti]


def cartella_caricamenti() -> Path:
    if os.environ.get("SGS_CARTELLA_CARICAMENTI"):
        return _normalizza(os.environ["SGS_CARTELLA_CARICAMENTI"])
    return cartelle_documenti()[0]


# Sola lettura: nessuna scrittura nelle cartelle sorgente, caricamento da interfaccia disattivato.
SOLA_LETTURA = _booleano("SGS_SOLA_LETTURA")

# «assistito» = ricerca locale + risposte del modello; «locale» = nessuna chiamata esterna,
# solo ricerca full-text e gestione dei registri.
MODALITA = os.environ.get("SGS_MODALITA", "assistito").strip().lower()
if MODALITA not in {"assistito", "locale"}:
    MODALITA = "assistito"

# Nomi/cartelle da non indicizzare mai (glob, confrontati su nome file e su ogni parte del percorso).
ESCLUSIONI: list[str] = _elenco(os.environ.get(
    "SGS_ESCLUDI",
    "~$*;*.tmp;*.bak;.*;Archivio storico*;Riservato*;Dati personali*;*Bozza*"))

PERCORSO_DB = Path(os.environ.get("SGS_DB", RADICE / "sgs_live.db")).resolve()
PORTA = int(os.environ.get("SGS_PORTA", "8770"))
INDIRIZZO = os.environ.get("SGS_INDIRIZZO", "127.0.0.1")
CARTELLA_WEB = RADICE / "web"

# Sistemi TGV presidiati (prefissi usati nella naming convention documentale).
SISTEMI = ["TGV", "MET", "FGC", "FPG", "FIL"]

# Tipologie previste dalla procedura di gestione della documentazione: sigla -> descrizione.
TIPI_DOCUMENTO = {
    # Documenti strategici di indirizzo e pianificazione
    "POL": "Politica della Sicurezza",
    "MSGS": "Manuale SGS",
    "MSRM": "Manuale SRM",
    "DVR": "Documento di Valutazione dei Rischi",
    "PAS": "Piano Annuale della Sicurezza",
    "RAS": "Relazione Annuale della Sicurezza",
    "RIS": "Riesame della Direzione per la Sicurezza",
    # Documenti organizzativi e operativi
    "PRC": "Procedura organizzativa",
    "IST": "Istruzione operativa",
    "RDE": "Regolamento di Esercizio",
    "ODS": "Ordine di Servizio",
    "RGS": "Registro",
    "MOD": "Modulo",
}
