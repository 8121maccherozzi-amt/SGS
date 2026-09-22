"""Ricerca full-text sui documenti SGS indicizzati (SQLite FTS5 + BM25)."""
from __future__ import annotations

import re

from .db import connessione

STOPWORD = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "del", "della", "dei", "delle",
    "dello", "degli", "da", "dal", "dalla", "in", "nel", "nella", "con", "su", "sul", "sulla",
    "per", "tra", "fra", "e", "ed", "o", "od", "che", "chi", "cui", "non", "come", "dove", "quando",
    "quale", "quali", "questo", "questa", "sono", "essere", "al", "allo", "alla", "ai", "agli",
    "alle", "a", "ha", "hanno", "mi", "mostrami", "dimmi", "trova", "cerca", "estratto", "parla",
    "documento", "documenti", "riguardo", "circa", "vorrei", "sapere", "qual", "cosa", "quali",
}

SINONIMI = {
    "formazione": ["formazione", "addestramento", "abilitazione", "competenze", "CDF"],
    "manutenzione": ["manutenzione", "manutentiv", "SRM", "officina"],
    "audit": ["audit", "verifica", "ispezione"],
    "rischio": ["rischio", "rischi", "pericolo", "hazard"],
    "indicatore": ["indicatore", "indicatori", "IPS", "prestazionale"],
    "norma": ["norma", "normativa", "normative", "riferimenti"],
    "veicoli": ["veicoli", "rotabil", "materiale rotabile", "vettur"],
    "incidente": ["incidente", "inconveniente", "evento"],
    "fornitore": ["fornitore", "fornitori", "appaltator", "interfaccia"],
}


def _termini(domanda: str) -> list[str]:
    grezzi = re.findall(r"[0-9A-Za-zÀ-ÿ_]{3,}", domanda.lower())
    termini: list[str] = []
    for t in grezzi:
        if t in STOPWORD:
            continue
        for s in SINONIMI.get(t, [t]):
            if s not in termini:
                termini.append(s)
    return termini[:14]


def _query_fts(termini: list[str]) -> str:
    pezzi = []
    for t in termini:
        pulito = re.sub(r'[^0-9A-Za-zÀ-ÿ_ ]', "", t).strip()
        if not pulito:
            continue
        if " " in pulito:
            pezzi.append(f'"{pulito}"')
        else:
            pezzi.append(f'{pulito}*' if len(pulito) > 4 else pulito)
    return " OR ".join(pezzi)


def cerca(domanda: str, *, sistema: str | None = None, tipo_documento: str | None = None,
          codice_documento: str | None = None, massimo: int = 6) -> list[dict]:
    """Restituisce i passaggi piu' pertinenti con riferimento a documento/pagina/sezione."""
    termini = _termini(domanda)
    if not termini:
        return []

    condizioni, parametri = ["chunk_fts MATCH ?"], [_query_fts(termini)]
    if sistema:
        condizioni.append("d.sistema = ?")
        parametri.append(sistema.upper())
    if tipo_documento:
        condizioni.append("d.tipo = ?")
        parametri.append(tipo_documento)
    if codice_documento:
        condizioni.append("d.codice LIKE ?")
        parametri.append(f"%{codice_documento}%")
    parametri.append(massimo)

    sql = f"""
        SELECT c.id AS chunk_id, c.pagina, c.sezione, c.testo,
               d.codice, d.titolo, d.tipo, d.sistema, d.revisione,
               bm25(chunk_fts, 4.0, 2.0) AS punteggio,
               snippet(chunk_fts, 0, '<<', '>>', ' … ', 24) AS evidenza
        FROM chunk_fts
        JOIN chunk c ON c.id = chunk_fts.rowid
        JOIN documenti d ON d.id = c.documento_id
        WHERE {' AND '.join(condizioni)}
        ORDER BY punteggio
        LIMIT ?
    """
    with connessione() as con:
        try:
            trovati = con.execute(sql, tuple(parametri)).fetchall()
        except Exception:
            return []
    return [dict(r) for r in trovati]


def estratto(chunk_id: int, *, contesto: int = 1) -> dict | None:
    """Testo integrale di un passaggio, con i chunk adiacenti come contesto."""
    with connessione() as con:
        base = con.execute(
            """SELECT c.*, d.codice, d.titolo, d.revisione, d.sistema, d.tipo
               FROM chunk c JOIN documenti d ON d.id = c.documento_id WHERE c.id=?""",
            (chunk_id,),
        ).fetchone()
        if not base:
            return None
        vicini = con.execute(
            """SELECT ordine, pagina, testo FROM chunk
               WHERE documento_id=? AND ordine BETWEEN ? AND ? ORDER BY ordine""",
            (base["documento_id"], base["ordine"] - contesto, base["ordine"] + contesto),
        ).fetchall()
    return {
        "codice": base["codice"], "titolo": base["titolo"], "revisione": base["revisione"],
        "sistema": base["sistema"], "tipo": base["tipo"], "pagina": base["pagina"],
        "sezione": base["sezione"], "chunk_id": chunk_id,
        "testo": "\n\n".join(v["testo"] for v in vicini),
    }
