"""Schema SQLite, accesso ai dati e registro di audit di SGS Live.

Regole architetturali (vincolanti per la tracciabilita' richiesta dal SGS):
  * nessuna scrittura avviene senza passare da `registra_audit`;
  * le modifiche proposte dall'assistente entrano come `proposte` in stato
    'in_attesa' e diventano effettive solo dopo conferma esplicita di un
    operatore identificato.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import PERCORSO_DB

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documenti (
    id INTEGER PRIMARY KEY,
    codice TEXT NOT NULL UNIQUE,
    titolo TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'Altro',
    sistema TEXT NOT NULL DEFAULT 'TGV',
    revisione TEXT,
    data_entrata_vigore TEXT,
    stato TEXT NOT NULL DEFAULT 'vigente',
    percorso TEXT NOT NULL,
    impronta TEXT NOT NULL,
    n_chunk INTEGER NOT NULL DEFAULT 0,
    indicizzato_il TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS chunk (
    id INTEGER PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES documenti(id) ON DELETE CASCADE,
    ordine INTEGER NOT NULL,
    pagina INTEGER,
    sezione TEXT,
    testo TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON chunk(documento_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    testo, sezione,
    content='chunk', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS chunk_ai AFTER INSERT ON chunk BEGIN
    INSERT INTO chunk_fts(rowid, testo, sezione) VALUES (new.id, new.testo, new.sezione);
END;
CREATE TRIGGER IF NOT EXISTS chunk_ad AFTER DELETE ON chunk BEGIN
    INSERT INTO chunk_fts(chunk_fts, rowid, testo, sezione) VALUES('delete', old.id, old.testo, old.sezione);
END;

-- TGV_MSGS_RGS_01 - Registro normative di riferimento
CREATE TABLE IF NOT EXISTS norme (
    id INTEGER PRIMARY KEY,
    riferimento TEXT NOT NULL UNIQUE,
    titolo TEXT NOT NULL,
    ente TEXT,
    tipo_atto TEXT,
    data_pubblicazione TEXT,
    data_entrata_vigore TEXT,
    sistemi TEXT NOT NULL DEFAULT 'TGV',
    ambito TEXT,
    stato TEXT NOT NULL DEFAULT 'vigente',
    sintesi_applicabilita TEXT,
    valutazione_impatto TEXT,
    azioni_conseguenti TEXT,
    responsabile TEXT,
    scadenza TEXT,
    documenti_sgs_impattati TEXT,
    note TEXT,
    creato_il TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL
);

-- TGV_PRC_06_RGS_02 - Registro Indicatori Prestazionali di Sicurezza
CREATE TABLE IF NOT EXISTS indicatori (
    id INTEGER PRIMARY KEY,
    codice TEXT NOT NULL,
    sistema TEXT NOT NULL DEFAULT 'TGV',
    descrizione TEXT NOT NULL,
    unita_misura TEXT,
    tipo TEXT NOT NULL DEFAULT 'reattivo',
    verso TEXT NOT NULL DEFAULT 'min',
    soglia_allarme REAL,
    soglia_intervento REAL,
    soglia_accettabilita TEXT,
    id_ep TEXT,
    responsabile TEXT,
    periodicita TEXT NOT NULL DEFAULT 'trimestrale',
    note TEXT,
    creato_il TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL,
    UNIQUE (codice, sistema)
);

CREATE TABLE IF NOT EXISTS misure (
    id INTEGER PRIMARY KEY,
    indicatore_id INTEGER NOT NULL REFERENCES indicatori(id) ON DELETE CASCADE,
    periodo TEXT NOT NULL,
    valore REAL NOT NULL,
    fonte TEXT,
    note TEXT,
    validato_ot INTEGER NOT NULL DEFAULT 0,
    inserito_da TEXT NOT NULL,
    inserito_il TEXT NOT NULL,
    UNIQUE (indicatore_id, periodo)
);

CREATE TABLE IF NOT EXISTS proposte (
    id INTEGER PRIMARY KEY,
    creata_il TEXT NOT NULL,
    sessione TEXT,
    utente TEXT,
    strumento TEXT NOT NULL,
    entita TEXT NOT NULL,
    riepilogo TEXT NOT NULL,
    motivazione TEXT,
    payload TEXT NOT NULL,
    anteprima TEXT,
    stato TEXT NOT NULL DEFAULT 'in_attesa',
    decisa_il TEXT,
    decisa_da TEXT,
    esito TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    utente TEXT NOT NULL,
    azione TEXT NOT NULL,
    entita TEXT NOT NULL,
    entita_id TEXT,
    prima TEXT,
    dopo TEXT,
    origine TEXT NOT NULL DEFAULT 'interfaccia',
    proposta_id INTEGER,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);

CREATE TABLE IF NOT EXISTS messaggi (
    id INTEGER PRIMARY KEY,
    sessione TEXT NOT NULL,
    ts TEXT NOT NULL,
    ruolo TEXT NOT NULL,
    contenuto TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messaggi_sessione ON messaggi(sessione, id);
"""


def adesso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connessione() -> sqlite3.Connection:
    Path(PERCORSO_DB).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(PERCORSO_DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def inizializza() -> None:
    with connessione() as con:
        con.executescript(SCHEMA)


def righe(sql: str, parametri: Iterable[Any] = ()) -> list[dict]:
    with connessione() as con:
        return [dict(r) for r in con.execute(sql, tuple(parametri)).fetchall()]


def riga(sql: str, parametri: Iterable[Any] = ()) -> dict | None:
    risultato = righe(sql, parametri)
    return risultato[0] if risultato else None


def registra_audit(
    con: sqlite3.Connection,
    *,
    utente: str,
    azione: str,
    entita: str,
    entita_id: str | int | None = None,
    prima: Any = None,
    dopo: Any = None,
    origine: str = "interfaccia",
    proposta_id: int | None = None,
    note: str | None = None,
) -> None:
    con.execute(
        """INSERT INTO audit_log (ts, utente, azione, entita, entita_id, prima, dopo,
                                  origine, proposta_id, note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            adesso(),
            utente,
            azione,
            entita,
            str(entita_id) if entita_id is not None else None,
            json.dumps(prima, ensure_ascii=False) if prima is not None else None,
            json.dumps(dopo, ensure_ascii=False) if dopo is not None else None,
            origine,
            proposta_id,
            note,
        ),
    )


def stato_indicatore(valore: float | None, ind: dict) -> str:
    """Classifica una misura rispetto alle soglie di Allarme/Intervento (TGV_PRC_11)."""
    if valore is None:
        return "non_misurato"
    allarme, intervento = ind.get("soglia_allarme"), ind.get("soglia_intervento")
    peggiore_sopra = (ind.get("verso") or "min") == "min"

    def supera(soglia: float | None) -> bool:
        if soglia is None:
            return False
        return valore > soglia if peggiore_sopra else valore < soglia

    if supera(intervento):
        return "intervento"
    if supera(allarme):
        return "allarme"
    return "ok"
