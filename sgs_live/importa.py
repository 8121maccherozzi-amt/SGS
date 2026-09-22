"""Travaso di un registro esistente (Excel o Word) nelle tabelle di SGS Live.

Il registro resta il documento ufficiale: qui se ne legge il contenuto per
popolare la tabella interrogabile, con anteprima e conferma dell'operatore e
registrazione in audit di ogni riga scritta.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from .db import adesso, connessione, registra_audit, riga
from .tools import CAMPI_NORMA

# Parole chiave per riconoscere le colonne: dalla più specifica alla più generica.
INDIZI: list[tuple[str, tuple[str, ...]]] = [
    ("data_entrata_vigore", ("entrata in vigore", "entrata vigore", "in vigore dal", "vigore")),
    ("data_pubblicazione", ("pubblicazione", "pubblicato", "emissione", "emanazione")),
    ("documenti_sgs_impattati", ("documenti sgs", "documenti impattati", "documenti collegati",
                                 "documentazione impattata", "procedure collegate", "collegamenti")),
    ("sintesi_applicabilita", ("sintesi", "applicabilit", "contenuto", "sintesi applicabilit")),
    ("valutazione_impatto", ("valutazione di impatto", "valutazione impatto", "impatto")),
    ("azioni_conseguenti", ("azioni", "adempiment", "attività conseguenti", "attivita conseguenti")),
    ("responsabile", ("responsabile", "funzione responsabile", "owner", "referente")),
    ("scadenza", ("scadenza", "termine", "entro il", "data limite")),
    ("tipo_atto", ("tipo di atto", "tipologia", "tipo atto", "tipo")),
    ("ente", ("ente", "emittente", "autorità", "autorita", "organismo", "fonte")),
    ("sistemi", ("sistemi", "sistema", "applicabile a", "ambito di applicazione", "linea")),
    ("stato", ("stato", "vigenza", "vigente")),
    ("ambito", ("ambito", "area", "processo", "materia", "argomento")),
    ("titolo", ("titolo", "oggetto", "denominazione", "descrizione")),
    ("riferimento", ("riferimento", "normativa", "norma", "estremi", "identificativo",
                     "atto", "documento")),
    ("note", ("note", "osservazioni", "annotazioni")),
]

STATI = {"vigente", "abrogata", "in_recepimento", "monitoraggio"}
RE_DATA = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})")


def _normalizza(valore: Any) -> str:
    if valore is None:
        return ""
    testo = str(valore).strip()
    return re.sub(r"\s+", " ", testo)


def tabelle(percorso: Path) -> list[dict]:
    """Tabelle contenute nel file: un foglio Excel, una tabella Word o un CSV."""
    suffisso = percorso.suffix.lower()
    uscita: list[dict] = []

    if suffisso in {".xlsx", ".xlsm"}:
        import openpyxl

        libro = openpyxl.load_workbook(str(percorso), read_only=True, data_only=True)
        try:
            for foglio in libro.worksheets:
                righe = [[_normalizza(c) for c in r]
                         for r in foglio.iter_rows(values_only=True, max_row=2000)]
                righe = [r for r in righe if any(r)]
                if righe:
                    uscita.append({"nome": foglio.title, "righe": righe})
        finally:
            libro.close()

    elif suffisso == ".docx":
        import docx

        documento = docx.Document(str(percorso))
        for numero, tabella in enumerate(documento.tables, start=1):
            righe = [[_normalizza(c.text) for c in r.cells] for r in tabella.rows]
            righe = [r for r in righe if any(r)]
            if righe:
                uscita.append({"nome": f"Tabella {numero}", "righe": righe})

    elif suffisso in {".csv", ".txt"}:
        with percorso.open(encoding="utf-8-sig", newline="") as f:
            campione = f.read(4096)
            f.seek(0)
            delimitatore = ";" if campione.count(";") >= campione.count(",") else ","
            righe = [[_normalizza(c) for c in r] for r in csv.reader(f, delimiter=delimitatore)]
        righe = [r for r in righe if any(r)]
        if righe:
            uscita.append({"nome": percorso.name, "righe": righe})

    return uscita


def trova_intestazione(righe: list[list[str]]) -> int:
    """Riga di intestazione: la prima con almeno due celle testuali che somigliano a titoli."""
    migliore, punteggio_migliore = 0, -1
    for indice, r in enumerate(righe[:15]):
        piene = [c for c in r if c]
        if len(piene) < 2:
            continue
        punteggio = len(piene)
        for c in piene:
            testo = c.lower()
            if any(k in testo for _, chiavi in INDIZI for k in chiavi):
                punteggio += 4
            if len(c) > 60 or RE_DATA.search(c):
                punteggio -= 3          # sembra un dato, non un titolo di colonna
        if punteggio > punteggio_migliore:
            migliore, punteggio_migliore = indice, punteggio
    return migliore


def proponi_mappatura(intestazioni: list[str]) -> dict[str, int]:
    """Associa ogni campo del registro alla colonna che gli somiglia di più."""
    mappatura: dict[str, int] = {}
    usate: set[int] = set()
    for campo, chiavi in INDIZI:
        for indice, testa in enumerate(intestazioni):
            if indice in usate or not testa:
                continue
            testo = testa.lower()
            if any(k in testo for k in chiavi):
                mappatura[campo] = indice
                usate.add(indice)
                break
    return mappatura


def anteprima(percorso: Path, foglio: str | None = None, massimo: int = 8) -> dict:
    trovate = tabelle(percorso)
    if not trovate:
        raise ValueError("Nessuna tabella leggibile nel documento.")
    scelta = next((t for t in trovate if t["nome"] == foglio), trovate[0])
    righe = scelta["righe"]
    indice = trova_intestazione(righe)
    intestazioni = righe[indice]
    dati = [r for r in righe[indice + 1:] if any(r)]
    return {
        "fogli": [t["nome"] for t in trovate],
        "foglio": scelta["nome"],
        "riga_intestazione": indice,
        "intestazioni": intestazioni,
        "mappatura": proponi_mappatura(intestazioni),
        "righe_totali": len(dati),
        "esempio": dati[:massimo],
        "campi": CAMPI_NORMA,
    }


def _valore(riga_dati: list[str], indice: int | None) -> str:
    if indice is None or indice < 0 or indice >= len(riga_dati):
        return ""
    return riga_dati[indice].strip()


def _data(valore: str) -> str:
    """Normalizza le date in AAAA-MM-GG, lasciando intatto ciò che non è una data."""
    valore = valore.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valore):
        return valore
    m = RE_DATA.search(valore)
    if not m:
        return valore[:40]
    giorno, mese, anno = m.groups()
    if len(anno) == 2:
        anno = f"20{anno}" if int(anno) < 70 else f"19{anno}"
    return f"{anno}-{int(mese):02d}-{int(giorno):02d}"


def importa_norme(documento_id: int, mappatura: dict[str, int], utente: str,
                  foglio: str | None = None, riga_intestazione: int | None = None) -> dict:
    """Scrive nel registro normative le righe lette dal documento. Ogni riga finisce in audit."""
    documento = riga("SELECT id, codice, titolo, percorso FROM documenti WHERE id=?", (documento_id,))
    if not documento:
        raise ValueError("Documento non trovato nell'indice.")
    percorso = Path(documento["percorso"])
    if not percorso.exists():
        raise ValueError("Il file non è più raggiungibile nella cartella sorgente.")
    if "riferimento" not in mappatura:
        raise ValueError("Indicare almeno la colonna del riferimento normativo.")

    trovate = tabelle(percorso)
    scelta = next((t for t in trovate if t["nome"] == foglio), trovate[0] if trovate else None)
    if not scelta:
        raise ValueError("Nessuna tabella leggibile nel documento.")
    righe = scelta["righe"]
    indice = riga_intestazione if riga_intestazione is not None else trova_intestazione(righe)

    inserite = aggiornate = saltate = 0
    with connessione() as con:
        for riga_dati in righe[indice + 1:]:
            campi: dict[str, str] = {}
            for campo, colonna in mappatura.items():
                if campo not in CAMPI_NORMA:
                    continue
                valore = _valore(riga_dati, colonna)
                if not valore:
                    continue
                if campo.startswith("data_") or campo == "scadenza":
                    valore = _data(valore)
                if campo == "stato":
                    normalizzato = valore.lower().replace(" ", "_")
                    valore = normalizzato if normalizzato in STATI else "vigente"
                campi[campo] = valore[:2000]

            riferimento = campi.get("riferimento", "")
            if len(riferimento) < 3:
                saltate += 1
                continue
            campi.setdefault("titolo", riferimento)
            campi.setdefault("stato", "vigente")
            campi["note"] = " · ".join(filter(None, [
                campi.get("note", ""), f"Importato da {documento['codice']}"]))[:2000]

            esistente = con.execute("SELECT * FROM norme WHERE lower(riferimento)=lower(?)",
                                    (riferimento,)).fetchone()
            if esistente:
                assegnazioni = ", ".join(f"{k}=?" for k in campi)
                con.execute(f"UPDATE norme SET {assegnazioni}, aggiornato_il=? WHERE id=?",
                            (*campi.values(), adesso(), esistente["id"]))
                record_id, azione, prima = esistente["id"], "norma_aggiornata_da_registro", dict(esistente)
                aggiornate += 1
            else:
                colonne = list(campi) + ["creato_il", "aggiornato_il"]
                con.execute(
                    f"INSERT INTO norme ({','.join(colonne)}) VALUES ({','.join('?' * len(colonne))})",
                    (*campi.values(), adesso(), adesso()))
                record_id = con.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
                azione, prima = "norma_importata", None
                inserite += 1

            registra_audit(con, utente=utente, azione=azione, entita="norme", entita_id=record_id,
                           prima=prima, dopo=campi, origine="importazione_registro",
                           note=f"da {documento['codice']} · foglio «{scelta['nome']}»")

    return {"inserite": inserite, "aggiornate": aggiornate, "saltate": saltate,
            "documento": documento["codice"], "foglio": scelta["nome"]}
