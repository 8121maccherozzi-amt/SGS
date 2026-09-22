"""Indicizzazione dei documenti SGS (PDF, DOCX, TXT, MD) in SQLite FTS5."""
from __future__ import annotations

import fnmatch
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .config import ESCLUSIONI, cartelle_documenti
from .db import adesso, connessione, registra_audit

ESTENSIONI = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".xlsm"}
MAX_CELLE_FOGLIO = 20000
DIM_CHUNK = 1400
SOVRAPPOSIZIONE = 200

from .config import TIPI_DOCUMENTO

# Naming convention: [SISTEMA_]SIGLA[_numero][_SOTTOSIGLA_numero]
# Es.: "TGV_PRC_11 - Monitoraggio prestazioni rev 02.pdf", "MET_PRC_06_RGS_02 Hazard Log.xlsx"
SIGLE = "|".join(TIPI_DOCUMENTO)
RE_CODICE = re.compile(
    rf"^(?:(TGV|MET|FGC|FPG|FIL|FER)[_\- ]?)?({SIGLE})(?:[_\- ]?(\d{{1,4}}))?"
    rf"(?:[_\- ]?(RGS|MOD|IST|ALL)[_\- ]?(\d{{1,4}}))?",
    re.IGNORECASE,
)
# Stesso schema non ancorato: intercetta i file rinominati («Copia di TGV_PRC_06 - …»).
RE_CODICE_OVUNQUE = re.compile(
    rf"(?<![A-Za-z0-9])(?:(TGV|MET|FGC|FPG|FIL|FER)[_\- ]?)?({SIGLE})(?:[_\- ]?(\d{{1,4}}))?"
    rf"(?:[_\- ]?(RGS|MOD|IST|ALL)[_\- ]?(\d{{1,4}}))?",
    re.IGNORECASE,
)
RE_SOLO_SISTEMA = re.compile(r"^(TGV|MET|FGC|FPG|FIL|FER)[_\- ]", re.IGNORECASE)
RE_REVISIONE = re.compile(r"\brev\.?\s*([0-9]{1,2}(?:\.[0-9]{1,2})?)", re.IGNORECASE)

# Le cartelle dell'archivio sono aree tematiche di processo, non tipologie di documento:
# il tipo si legge dalla sigla nel nome del file, il tema dalla cartella.
RE_NUMERAZIONE = re.compile(r"^\s*[0-9]{1,3}\s*[\.\-_)]\s*|^\s*[0-9]{1,3}\s+")

TEMI = [
    ("Manuale SGS", ("manuale sgs", "manuale del sgs", "manuale")),
    ("Procedure Organizzative", ("procedure organizzative", "procedure", "procedura")),
    ("Formazione", ("formazione", "addestramento", "abilitazion", "competenz", "cdf", "sgc")),
    ("Valutazione dei rischi", ("valutazione dei rischi", "valutazione rischi", "rischi", "rischio",
                                 "hazard", "evento pericoloso", "eventi pericolosi", "dvr")),
    ("Regolamento di Esercizio", ("regolamento di esercizio", "regolamento", "circolazione",
                                   "emergenza", "evacuazione", "rde")),
    ("Manutenzione Infrastruttura", ("manutenzione infrastruttura", "infrastruttura", "armamento",
                                      "binario", "linea aerea", "sottostazion", "impianti fissi")),
    ("Manutenzione Veicoli - SRM", ("manutenzione veicoli", "veicoli", "rotabil", "srm",
                                     "officina", "msrm")),
    ("Monitoraggio", ("monitoraggio", "indicator", "ips", "prestazioni di sicurezza")),
    ("Non Conformità ed Eventi Indesiderati", ("non conformit", "eventi indesiderati",
                                                "evento indesiderato", "incident", "inconvenient",
                                                "prescrizion", "anormalit")),
]

SISTEMA_DA_CARTELLA = [
    (("metropolitana", "metro"), "MET"),
    (("genova casella", "casella", "ferrovia genova"), "FGC"),
    (("principe granarolo", "granarolo"), "FPG"),
    (("filovia", "filoviaria", "filobus"), "FIL"),
    (("comune", "comuni", "trasversale", "guida vincolata"), "TGV"),
]


def nome_pulito(nome: str) -> str:
    """«1 - Manuale SGS» e «Manuale SGS» sono la stessa cartella: la numerazione non conta."""
    return RE_NUMERAZIONE.sub("", nome).strip().lower()


def tema_da_cartella(nome: str) -> str:
    """Riconduce il nome della cartella a un'area tematica nota; altrimenti lo restituisce pulito."""
    pulito = nome_pulito(nome)
    for canonico, chiavi in TEMI:
        if any(k in pulito for k in chiavi):
            return canonico
    return RE_NUMERAZIONE.sub("", nome).strip() or nome


def metadati_da_cartelle(nomi: list[str]) -> dict:
    """Tema (dalla cartella più esterna) e, come ripiego, sistema se la cartella lo nomina."""
    trovati: dict[str, str] = {}
    if nomi:
        trovati["tema"] = tema_da_cartella(nomi[0])
    for nome in nomi:
        pulito = nome_pulito(nome)
        for chiavi, sistema in SISTEMA_DA_CARTELLA:
            if any(k in pulito for k in chiavi):
                trovati["sistema"] = sistema
    return trovati


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
    """Deduce codice, tipologia, sistema, revisione e documento padre dal nome del file.

    La tipologia viene SEMPRE dalla sigla (POL, MSGS, PRC, IST, RDE, RGS, MOD, ...):
    è l'unico dato che la stabilisce, perché le cartelle esprimono il tema.
    """
    nome = percorso.stem
    sistema, tipo, codice, padre = "TGV", "Altro", None, None

    m = RE_CODICE.match(nome) or RE_CODICE_OVUNQUE.search(nome)
    if m and m.group(2):
        sigla = m.group(2).upper()
        tipo = TIPI_DOCUMENTO.get(sigla, "Altro")
        if m.group(1):
            sistema = m.group(1).upper()
            if sistema == "FER":        # riferimenti legacy: FER_PRC_xx equivale a TGV_PRC_xx
                sistema = "TGV"
        parti = [sistema, sigla]
        if m.group(3):
            parti.append(m.group(3).zfill(2))
        if m.group(4) and m.group(5):
            sottosigla = m.group(4).upper()
            padre = "_".join(parti)      # es. TGV_PRC_06 per TGV_PRC_06_RGS_01
            parti.extend([sottosigla, m.group(5).zfill(2)])
            tipo = TIPI_DOCUMENTO.get(sottosigla, tipo)
        codice = "_".join(parti)
        resto = (nome[:m.start()] + " " + nome[m.end():])
    else:
        prefisso = RE_SOLO_SISTEMA.match(nome)
        if prefisso:
            sistema = prefisso.group(1).upper()
            if sistema == "FER":
                sistema = "TGV"
        resto = nome

    titolo = re.sub(r"\s+", " ", RE_REVISIONE.sub("", resto)).strip(" -–—_.")
    rev = RE_REVISIONE.search(nome)
    return {
        "codice": codice or nome[:80],
        "titolo": titolo or codice or nome,
        "tipo": tipo,
        "sistema": sistema,
        "revisione": rev.group(1) if rev else None,
        "padre": padre,
    }


def escluso(percorso: Path) -> bool:
    """Vero se il file, o una qualsiasi cartella del suo percorso, ricade in un'esclusione."""
    parti = [percorso.name, *[p.name for p in percorso.parents]]
    for modello in ESCLUSIONI:
        for parte in parti:
            if fnmatch.fnmatch(parte.lower(), modello.lower()):
                return True
    return False


def _testo_pdf(percorso: Path) -> list[tuple[int | None, str | None, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(percorso))
    return [(i + 1, None, (p.extract_text() or "")) for i, p in enumerate(reader.pages)]


def _testo_xlsx(percorso: Path) -> list[tuple[int | None, str | None, str]]:
    """Registri in Excel (Hazard Log, registro IPS, registro NC): un blocco per foglio."""
    import openpyxl

    libro = openpyxl.load_workbook(str(percorso), read_only=True, data_only=True)
    fogli: list[tuple[int | None, str | None, str]] = []
    try:
        for foglio in libro.worksheets:
            righe_testo, celle = [], 0
            for riga in foglio.iter_rows(values_only=True):
                valori = [str(v).strip().replace("\n", " ") for v in riga if v not in (None, "")]
                celle += len(valori)
                if valori:
                    righe_testo.append(" | ".join(valori))
                if celle > MAX_CELLE_FOGLIO:
                    righe_testo.append("[…foglio troncato in indicizzazione…]")
                    break
            if righe_testo:
                fogli.append((None, f"Foglio «{foglio.title}»", "\n".join(righe_testo)))
    finally:
        libro.close()
    return fogli


def _testo_docx(percorso: Path) -> list[tuple[int | None, str | None, str]]:
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
    return [(None, None, "\n".join(parti))]


def estrai(percorso: Path) -> list[tuple[int | None, str | None, str]]:
    """Restituisce blocchi (pagina, sezione imposta, testo) a seconda del formato."""
    suffisso = percorso.suffix.lower()
    if suffisso == ".pdf":
        return _testo_pdf(percorso)
    if suffisso == ".docx":
        return _testo_docx(percorso)
    if suffisso in {".xlsx", ".xlsm"}:
        return _testo_xlsx(percorso)
    return [(None, None, percorso.read_text(encoding="utf-8", errors="replace"))]


RE_SEZIONE = re.compile(
    r"^\s*(?:##\s*)?((?:\d{1,2}(?:\.\d{1,2}){0,3})[.)]?\s+[A-ZÀ-Ù][^\n]{3,80}|[A-ZÀ-Ù][A-ZÀ-Ù \-']{6,60})\s*$"
)


def spezza(pagine: list[tuple[int | None, str | None, str]]) -> list[Pezzo]:
    pezzi: list[Pezzo] = []
    ordine = 0
    sezione_corrente: str | None = None

    for pagina, sezione_imposta, testo in pagine:
        if sezione_imposta:
            sezione_corrente = sezione_imposta
        testo = re.sub(r"[ \t]+", " ", testo or "").strip()
        if not testo:
            continue
        blocchi: list[tuple[str, str | None]] = []
        corrente = ""
        sezione_blocco = sezione_corrente
        for riga in testo.splitlines():
            m = None if sezione_imposta else RE_SEZIONE.match(riga)
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
            if len(testo_blocco) < 20:
                continue
            pezzi.append(Pezzo(ordine=ordine, pagina=pagina, sezione=sezione, testo=testo_blocco))
            ordine += 1
    return pezzi


def _codice_disponibile(con, codice: str, percorso: Path) -> tuple[str, dict | None]:
    """Evita che due file diversi con lo stesso nome-codice si sovrascrivano a vicenda."""
    per_percorso = con.execute("SELECT * FROM documenti WHERE percorso=?", (str(percorso),)).fetchone()
    if per_percorso:
        return per_percorso["codice"], dict(per_percorso)

    candidato, contatore = codice, 1
    while True:
        occupante = con.execute("SELECT * FROM documenti WHERE codice=?", (candidato,)).fetchone()
        if occupante is None:
            return candidato, None
        if not Path(occupante["percorso"]).exists():
            return candidato, dict(occupante)      # il vecchio file non c'è più: si riusa il codice
        contatore += 1
        candidato = f"{codice}#{contatore}"


def indicizza_file(percorso: Path, *, utente: str = "sistema", forza: bool = False,
                   cartella: Path | None = None) -> dict:
    meta = metadati_da_nome(percorso)
    impronta = _impronta(percorso)

    # Cartelle che contengono il documento, relative alla radice configurata.
    nomi_cartelle: list[str] = []
    if cartella:
        try:
            nomi_cartelle = list(percorso.relative_to(cartella).parts[:-1])
        except ValueError:
            nomi_cartelle = []
    percorso_relativo = "/".join(nomi_cartelle)

    dalle_cartelle = metadati_da_cartelle(nomi_cartelle)
    tema = dalle_cartelle.get("tema", "")
    if not RE_CODICE.match(percorso.stem) and dalle_cartelle.get("sistema"):
        meta["sistema"] = dalle_cartelle["sistema"]

    # Il contesto cercabile comprende tema e sottocartelle: nominarli in una domanda
    # deve bastare a recuperare i documenti che stanno lì.
    contesto = " · ".join(filter(None, [
        meta["codice"], meta["titolo"], meta["tipo"], meta.get("padre"), tema,
        " / ".join(nomi_cartelle)]))

    with connessione() as con:
        meta["codice"], esistente = _codice_disponibile(con, meta["codice"], percorso)

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
                """UPDATE documenti SET codice=?, titolo=?, tipo=?, sistema=?, revisione=?,
                       percorso=?, impronta=?, n_chunk=?, indicizzato_il=?, cartella=?,
                       percorso_relativo=?, tema=?, padre=? WHERE id=?""",
                (meta["codice"], meta["titolo"], meta["tipo"], meta["sistema"], meta["revisione"],
                 str(percorso), impronta, len(pezzi), adesso(),
                 str(cartella) if cartella else None, percorso_relativo, tema,
                 meta.get("padre"), doc_id),
            )
            azione = "reindicizzato"
        else:
            cur = con.execute(
                """INSERT INTO documenti (codice, titolo, tipo, sistema, revisione, percorso,
                                          impronta, n_chunk, indicizzato_il, cartella,
                                          percorso_relativo, tema, padre)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (meta["codice"], meta["titolo"], meta["tipo"], meta["sistema"], meta["revisione"],
                 str(percorso), impronta, len(pezzi), adesso(),
                 str(cartella) if cartella else None, percorso_relativo, tema,
                 meta.get("padre")),
            )
            doc_id = cur.lastrowid
            azione = "indicizzato"

        con.executemany(
            """INSERT INTO chunk (documento_id, ordine, pagina, sezione, contesto, testo)
               VALUES (?,?,?,?,?,?)""",
            [(doc_id, p.ordine, p.pagina, p.sezione,
              " · ".join(filter(None, [contesto, p.sezione])), p.testo) for p in pezzi],
        )
        registra_audit(con, utente=utente, azione=f"documento_{azione}", entita="documenti",
                       entita_id=doc_id, dopo={**meta, "tema": tema, "cartelle": percorso_relativo,
                                               "chunk": len(pezzi)}, origine="indicizzazione")

    return {"codice": meta["codice"], "titolo": meta["titolo"], "stato": azione,
            "chunk": len(pezzi), "tema": tema, "cartelle": percorso_relativo}


def conta_indicizzabili(cartella: Path) -> dict:
    """Quanti file utili contiene una cartella: serve a capire perché l'indice resta vuoto."""
    cartella = Path(cartella)
    if not cartella.exists():
        return {"raggiungibile": False, "utili": 0, "esclusi": 0, "altri": 0}
    utili = esclusi = altri = 0
    for percorso in cartella.rglob("*"):
        if not percorso.is_file():
            continue
        if percorso.suffix.lower() not in ESTENSIONI:
            altri += 1
        elif escluso(percorso):
            esclusi += 1
        else:
            utili += 1
    return {"raggiungibile": True, "utili": utili, "esclusi": esclusi, "altri": altri}


def _sotto(percorso: Path, radici: list[Path]) -> bool:
    for radice in radici:
        try:
            percorso.relative_to(radice)
            return True
        except ValueError:
            continue
    return False


def rimuovi_mancanti(*, utente: str = "sistema", radici: list[Path] | None = None) -> list[str]:
    """Toglie dall'indice i documenti non più raggiungibili o non più sotto le cartelle sorgente."""
    rimossi = []
    with connessione() as con:
        for d in con.execute("SELECT id, codice, percorso FROM documenti").fetchall():
            percorso = Path(d["percorso"])
            fuori_perimetro = radici is not None and not _sotto(percorso, radici)
            if percorso.exists() and not fuori_perimetro:
                continue
            motivo = ("non più incluso nelle cartelle sorgente" if fuori_perimetro
                      else "file non più presente nella cartella sorgente")
            con.execute("DELETE FROM chunk WHERE documento_id=?", (d["id"],))
            con.execute("DELETE FROM documenti WHERE id=?", (d["id"],))
            registra_audit(con, utente=utente, azione="documento_rimosso", entita="documenti",
                           entita_id=d["id"], prima=dict(d), origine="indicizzazione", note=motivo)
            rimossi.append(d["codice"])
    return rimossi


def indicizza_cartella(cartelle: list[Path] | Path | None = None, *, utente: str = "sistema",
                       forza: bool = False, pulisci: bool = True) -> list[dict]:
    """Indicizza, in sola lettura, tutte le cartelle sorgente configurate."""
    if cartelle is None:
        radici = cartelle_documenti()
    elif isinstance(cartelle, (str, Path)):
        radici = [Path(cartelle)]
    else:
        radici = [Path(c) for c in cartelle]

    esiti: list[dict] = []
    for radice in radici:
        if not radice.exists():
            esiti.append({"codice": str(radice), "stato": "cartella_assente",
                          "errore": "percorso non raggiungibile (condivisione non montata?)"})
            continue
        for percorso in sorted(radice.rglob("*")):
            if not percorso.is_file() or percorso.suffix.lower() not in ESTENSIONI:
                continue
            if escluso(percorso):
                esiti.append({"codice": percorso.name, "stato": "escluso"})
                continue
            try:
                esiti.append(indicizza_file(percorso, utente=utente, forza=forza, cartella=radice))
            except Exception as exc:      # un file illeggibile non deve fermare il lotto
                esiti.append({"codice": percorso.name, "stato": "errore", "errore": str(exc)})

    # Quando si indicizza l'insieme completo, l'indice deve rispecchiare solo quelle cartelle.
    if pulisci:
        perimetro = radici if cartelle is None else None
        for codice in rimuovi_mancanti(utente=utente, radici=perimetro):
            esiti.append({"codice": codice, "stato": "rimosso"})
    return esiti
