"""Indicizzazione dei documenti SGS (PDF, DOCX, TXT, MD) in SQLite FTS5."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .config import CARTELLA_DOCUMENTI
from .db import adesso, connessione, registra_audit

ESTENSIONI = {".pdf", ".docx", ".txt", ".md"}
DIM_CHUNK = 1400
SOVRAPPOSIZIONE = 200

TIPO_DA_CODICE = {
    "MSGS": "Manuale",
    "PRC": "Procedura",
    "IO": "Istruzione Operativa",
    "RGS": "Registro",
    "MOD": "Modulo",
    "NE": "Norma di Esercizio",
    "ODS": "Ordine di Servizio",
    "DVR": "Registro",
    "POL": "Politica della Sicurezza",
}

# Es.: "TGV_PRC_11 - Monitoraggio prestazioni rev 02.pdf", "MET_PRC_06_RGS_02 Hazard Log.xlsx"
RE_CODICE = re.compile(
    r"^(TGV|MET|FGC|FPG|FIL|FER)[_\- ]?(MSGS|PRC|IO|MOD|NE|ODS|DVR|POL)?[_\- ]?(\d{1,3})?"
    r"(?:[_\- ]?(RGS|MOD|IO|ALL)[_\- ]?(\d{1,3}))?",
    re.IGNORECASE,
)
RE_REVISIONE = re.compile(r"\brev\.?\s*([0-9]{1,2}(?:\.[0-9]{1,2})?)", re.IGNORECASE)


@dataclass
class Pezzo:
    ordine: int
    pagina: int | None
    sezione: str | None
    testo: str


def _impronta(percorso: Path) -> str:
    h = hashlib.sha256()
    h.update(percorso.read_bytes())
    return h.hexdigest()[:32]


def metadati_da_nome(percorso: Path) -> dict:
    """Deduce codice / tipo / sistema / revisione dal nome file (naming TGV_PRC_xx)."""
    nome = percorso.stem
    sistema, tipo, codice = "TGV", "Altro", None

    m = RE_CODICE.match(nome)
    if m and m.group(1):
        sistema = m.group(1).upper()
        if sistema == "FER":          # riferimenti legacy: FER_PRC_xx == TGV_PRC_xx
            sistema = "TGV"
        parti = [sistema]
        if m.group(2):
            parti.append(m.group(2).upper())
            tipo = TIPO_DA_CODICE.get(m.group(2).upper(), "Altro")
        if m.group(3):
            parti.append(m.group(3).zfill(2))
        if m.group(4) and m.group(5):
            parti.extend([m.group(4).upper(), m.group(5).zfill(2)])
            tipo = TIPO_DA_CODICE.get(m.group(4).upper(), tipo)
        if len(parti) > 1:
            codice = "_".join(parti)

    titolo = nome
    for separatore in (" - ", " – ", " — "):
        if separatore in nome:
            titolo = nome.split(separatore, 1)[1].strip()
            break
    else:
        if codice:
            titolo = nome[len(nome.split()[0]):].strip(" -_–—") or nome

    rev = RE_REVISIONE.search(nome)
    return {
        "codice": codice or nome[:80],
        "titolo": RE_REVISIONE.sub("", titolo).strip(" -_") or nome,
        "tipo": tipo,
        "sistema": sistema,
        "revisione": rev.group(1) if rev else None,
    }


def _testo_pdf(percorso: Path) -> list[tuple[int | None, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(percorso))
    return [(i + 1, (p.extract_text() or "")) for i, p in enumerate(reader.pages)]


def _testo_docx(percorso: Path) -> list[tuple[int | None, str]]:
    import docx

    d = docx.Document(str(percorso))
    parti: list[str] = []
    for par in d.paragraphs:
        testo = par.text.strip()
        if not testo:
            continue
        if (par.style.name or "").lower().startswith("heading"):
            parti.append(f"\n## {testo}\n")
        else:
            parti.append(testo)
    for tabella in d.tables:
        for r in tabella.rows:
            celle = [c.text.strip().replace("\n", " ") for c in r.cells]
            if any(celle):
                parti.append(" | ".join(celle))
    return [(None, "\n".join(parti))]


def estrai(percorso: Path) -> list[tuple[int | None, str]]:
    suffisso = percorso.suffix.lower()
    if suffisso == ".pdf":
        return _testo_pdf(percorso)
    if suffisso == ".docx":
        return _testo_docx(percorso)
    return [(None, percorso.read_text(encoding="utf-8", errors="replace"))]


RE_SEZIONE = re.compile(
    r"^\s*(?:##\s*)?((?:\d{1,2}(?:\.\d{1,2}){0,3})[.)]?\s+[A-ZÀ-Ù][^\n]{3,80}|[A-ZÀ-Ù][A-ZÀ-Ù \-']{6,60})\s*$"
)


def spezza(pagine: list[tuple[int | None, str]]) -> list[Pezzo]:
    pezzi: list[Pezzo] = []
    ordine = 0
    sezione_corrente: str | None = None

    for pagina, testo in pagine:
        testo = re.sub(r"[ \t]+", " ", testo or "").strip()
        if not testo:
            continue
        blocchi: list[tuple[str, str | None]] = []
        corrente = ""
        sezione_blocco = sezione_corrente
        for riga in testo.splitlines():
            m = RE_SEZIONE.match(riga)
            if m:
                if corrente.strip():
                    blocchi.append((corrente.strip(), sezione_blocco))
                    corrente = ""
                sezione_corrente = m.group(1).strip()[:120]
                sezione_blocco = sezione_corrente
            corrente += riga + "\n"
            if len(corrente) >= DIM_CHUNK:
                blocchi.append((corrente.strip(), sezione_blocco))
                corrente = corrente[-SOVRAPPOSIZIONE:]
                sezione_blocco = sezione_corrente
        if corrente.strip():
            blocchi.append((corrente.strip(), sezione_blocco))

        for testo_blocco, sezione in blocchi:
            if len(testo_blocco) < 40:
                continue
            pezzi.append(Pezzo(ordine=ordine, pagina=pagina, sezione=sezione, testo=testo_blocco))
            ordine += 1
    return pezzi


def indicizza_file(percorso: Path, *, utente: str = "sistema", forza: bool = False) -> dict:
    meta = metadati_da_nome(percorso)
    impronta = _impronta(percorso)

    with connessione() as con:
        esistente = con.execute(
            "SELECT id, impronta, n_chunk FROM documenti WHERE codice=? OR percorso=?",
            (meta["codice"], str(percorso)),
        ).fetchone()

        if esistente and esistente["impronta"] == impronta and not forza:
            return {"codice": meta["codice"], "stato": "invariato", "chunk": esistente["n_chunk"]}

        pezzi = spezza(estrai(percorso))
        if not pezzi:
            return {"codice": meta["codice"], "stato": "vuoto", "chunk": 0,
                    "avviso": "nessun testo estraibile (PDF scansionato? serve OCR)"}

        if esistente:
            doc_id = esistente["id"]
            con.execute("DELETE FROM chunk WHERE documento_id=?", (doc_id,))
            con.execute(
                """UPDATE documenti SET titolo=?, tipo=?, sistema=?, revisione=?, percorso=?,
                       impronta=?, n_chunk=?, indicizzato_il=? WHERE id=?""",
                (meta["titolo"], meta["tipo"], meta["sistema"], meta["revisione"],
                 str(percorso), impronta, len(pezzi), adesso(), doc_id),
            )
            azione = "reindicizzato"
        else:
            cur = con.execute(
                """INSERT INTO documenti (codice, titolo, tipo, sistema, revisione, percorso,
                                          impronta, n_chunk, indicizzato_il)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (meta["codice"], meta["titolo"], meta["tipo"], meta["sistema"], meta["revisione"],
                 str(percorso), impronta, len(pezzi), adesso()),
            )
            doc_id = cur.lastrowid
            azione = "indicizzato"

        con.executemany(
            "INSERT INTO chunk (documento_id, ordine, pagina, sezione, testo) VALUES (?,?,?,?,?)",
            [(doc_id, p.ordine, p.pagina, p.sezione, p.testo) for p in pezzi],
        )
        registra_audit(con, utente=utente, azione=f"documento_{azione}", entita="documenti",
                       entita_id=doc_id, dopo={**meta, "chunk": len(pezzi)}, origine="indicizzazione")

    return {"codice": meta["codice"], "titolo": meta["titolo"], "stato": azione, "chunk": len(pezzi)}


def indicizza_cartella(cartella: Path | None = None, *, utente: str = "sistema",
                       forza: bool = False) -> list[dict]:
    cartella = Path(cartella or CARTELLA_DOCUMENTI)
    cartella.mkdir(parents=True, exist_ok=True)
    esiti: list[dict] = []
    for percorso in sorted(cartella.rglob("*")):
        if percorso.is_file() and percorso.suffix.lower() in ESTENSIONI:
            try:
                esiti.append(indicizza_file(percorso, utente=utente, forza=forza))
            except Exception as exc:  # un file illeggibile non deve fermare il lotto
                esiti.append({"codice": percorso.name, "stato": "errore", "errore": str(exc)})
    return esiti
