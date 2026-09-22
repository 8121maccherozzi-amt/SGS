"""SGS Live — API HTTP e servizio della dashboard."""
from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import agent, tools
from .config import (CARTELLA_DOCUMENTI, CARTELLE_DOCUMENTI, CARTELLA_WEB, ESCLUSIONI, MODALITA,
                     MODELLO, SISTEMI, SOLA_LETTURA, TIPI_DOCUMENTO)
from .db import adesso, connessione, inizializza, registra_audit, riga, righe, stato_indicatore
from .ingest import ESTENSIONI, indicizza_cartella
from .retrieval import cerca as cerca_passaggi

app = FastAPI(title="SGS Live", version="1.0")
inizializza()


@app.get("/")
def home() -> FileResponse:
    return FileResponse(CARTELLA_WEB / "index.html")


@app.get("/api/configurazione")
def configurazione() -> dict:
    return {
        "modello": MODELLO if MODALITA == "assistito" else None,
        "modalita": MODALITA,
        "sola_lettura": SOLA_LETTURA,
        "sistemi": SISTEMI,
        "tipi_documento": TIPI_DOCUMENTO,
        "estensioni": sorted(ESTENSIONI),
        "esclusioni": ESCLUSIONI,
        "cartelle_documenti": [
            {"percorso": str(c), "raggiungibile": c.exists()} for c in CARTELLE_DOCUMENTI],
        "cartella_caricamenti": str(CARTELLA_DOCUMENTI) if not SOLA_LETTURA else None,
    }


# ------------------------------------------------------------------ stato ----

@app.get("/api/stato")
def stato() -> dict:
    documenti = riga("SELECT COUNT(*) n, COALESCE(SUM(n_chunk),0) c FROM documenti") or {}
    norme_vigenti = riga("SELECT COUNT(*) n FROM norme WHERE stato='vigente'") or {}
    norme_recepimento = riga("SELECT COUNT(*) n FROM norme WHERE stato='in_recepimento'") or {}
    scadenze = righe(
        """SELECT riferimento, titolo, scadenza, responsabile, azioni_conseguenti FROM norme
           WHERE scadenza IS NOT NULL AND scadenza <> '' AND stato <> 'abrogata'
           ORDER BY scadenza LIMIT 8""")
    in_attesa = riga("SELECT COUNT(*) n FROM proposte WHERE stato='in_attesa'") or {}

    indicatori = _indicatori_con_stato()
    fuori_soglia = [i for i in indicatori if i["stato_soglia"] in ("allarme", "intervento")]
    return {
        "documenti": documenti.get("n", 0),
        "passaggi_indicizzati": documenti.get("c", 0),
        "norme_vigenti": norme_vigenti.get("n", 0),
        "norme_in_recepimento": norme_recepimento.get("n", 0),
        "indicatori": len(indicatori),
        "indicatori_fuori_soglia": len(fuori_soglia),
        "proposte_in_attesa": in_attesa.get("n", 0),
        "prossime_scadenze": scadenze,
        "criticita": [{"codice": i["codice"], "sistema": i["sistema"], "descrizione": i["descrizione"],
                       "valore": i["ultima_misura"], "periodo": i["ultimo_periodo"],
                       "stato": i["stato_soglia"]} for i in fuori_soglia],
    }


# --------------------------------------------------------------- dialogo -----

@app.post("/api/ricerca")
def ricerca(corpo: dict = Body(...)) -> dict:
    """Ricerca documentale senza modello: nessun dato esce dalla macchina."""
    domanda = (corpo.get("domanda") or "").strip()
    if not domanda:
        raise HTTPException(400, "Richiesta vuota.")
    risultati = cerca_passaggi(domanda, sistema=corpo.get("sistema") or None,
                               massimo=int(corpo.get("massimo", 8)))
    return {"risultati": [
        {"chunk_id": r["chunk_id"], "codice": r["codice"], "titolo": r["titolo"],
         "revisione": r["revisione"], "pagina": r["pagina"], "sezione": r["sezione"],
         "testo": r["testo"], "evidenza": r["evidenza"]} for r in risultati]}


@app.post("/api/chat")
def chat(corpo: dict = Body(...)) -> dict:
    if MODALITA == "locale":
        raise HTTPException(409, "Modalità locale attiva: l'assistente è disattivato e nessun dato "
                                 "viene inviato all'esterno. Usare la ricerca documentale.")
    domanda = (corpo.get("domanda") or "").strip()
    if not domanda:
        raise HTTPException(400, "Domanda vuota.")
    try:
        return agent.rispondi(domanda, sessione=corpo.get("sessione") or "default",
                              utente=corpo.get("utente") or "operatore")
    except Exception as exc:
        raise HTTPException(502, f"Errore nella chiamata al modello: {exc}")


@app.get("/api/conversazione/{sessione}")
def conversazione(sessione: str) -> list[dict]:
    """Solo i turni leggibili (testo utente e risposte finali)."""
    uscita = []
    for m in righe("SELECT ruolo, ts, contenuto FROM messaggi WHERE sessione=? ORDER BY id", (sessione,)):
        contenuto = json.loads(m["contenuto"])
        if m["ruolo"] == "user" and isinstance(contenuto, str):
            uscita.append({"ruolo": "utente", "ts": m["ts"], "testo": contenuto})
        elif m["ruolo"] == "assistant" and isinstance(contenuto, list):
            testo = "\n".join(b.get("text", "") for b in contenuto if b.get("type") == "text").strip()
            if testo:
                uscita.append({"ruolo": "assistente", "ts": m["ts"], "testo": testo})
    return uscita


@app.delete("/api/conversazione/{sessione}")
def azzera_conversazione(sessione: str) -> dict:
    with connessione() as con:
        con.execute("DELETE FROM messaggi WHERE sessione=?", (sessione,))
    return {"ok": True}


# -------------------------------------------------------------- proposte -----

@app.get("/api/proposte")
def elenco_proposte(stato: str = "in_attesa", limite: int = 50) -> list[dict]:
    sql = "SELECT * FROM proposte"
    par: list[Any] = []
    if stato != "tutte":
        sql += " WHERE stato=?"
        par.append(stato)
    elenco = righe(sql + " ORDER BY id DESC LIMIT ?", par + [limite])
    for p in elenco:
        p["payload"] = json.loads(p["payload"])
        p["anteprima"] = json.loads(p["anteprima"] or "{}")
    return elenco


@app.post("/api/proposte/{proposta_id}/conferma")
def conferma(proposta_id: int, corpo: dict = Body(default={})) -> dict:
    utente = (corpo.get("utente") or "").strip()
    if not utente:
        raise HTTPException(400, "Indicare l'operatore che conferma: la modifica va tracciata.")
    try:
        return tools.applica_proposta(proposta_id, utente)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/proposte/{proposta_id}/rifiuta")
def rifiuta(proposta_id: int, corpo: dict = Body(default={})) -> dict:
    utente = (corpo.get("utente") or "").strip()
    if not utente:
        raise HTTPException(400, "Indicare l'operatore che rifiuta.")
    try:
        return tools.rifiuta_proposta(proposta_id, utente, corpo.get("motivo", ""))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


# ----------------------------------------------------------------- norme -----

@app.get("/api/norme")
def elenco_norme(testo: str = "", sistema: str = "", stato: str = "") -> list[dict]:
    sql, par = "SELECT * FROM norme WHERE 1=1", []
    if testo:
        sql += " AND (riferimento LIKE ? OR titolo LIKE ? OR ambito LIKE ? OR sintesi_applicabilita LIKE ?)"
        par += [f"%{testo}%"] * 4
    if sistema:
        sql += " AND sistemi LIKE ?"
        par.append(f"%{sistema}%")
    if stato:
        sql += " AND stato=?"
        par.append(stato)
    return righe(sql + " ORDER BY riferimento", par)


@app.post("/api/norme")
def salva_norma(corpo: dict = Body(...)) -> dict:
    utente = (corpo.pop("utente", "") or "").strip()
    if not utente:
        raise HTTPException(400, "Indicare l'operatore.")
    campi = {k: v for k, v in corpo.items() if k in tools.CAMPI_NORMA}
    if not campi.get("riferimento"):
        raise HTTPException(400, "Riferimento obbligatorio.")
    with connessione() as con:
        esistente = con.execute("SELECT * FROM norme WHERE lower(riferimento)=lower(?)",
                                (campi["riferimento"],)).fetchone()
        if esistente:
            con.execute(f"UPDATE norme SET {', '.join(f'{k}=?' for k in campi)}, aggiornato_il=? WHERE id=?",
                        (*campi.values(), adesso(), esistente["id"]))
            record_id = esistente["id"]
        else:
            campi.setdefault("titolo", campi["riferimento"])
            colonne = list(campi) + ["creato_il", "aggiornato_il"]
            con.execute(f"INSERT INTO norme ({','.join(colonne)}) VALUES ({','.join('?' * len(colonne))})",
                        (*campi.values(), adesso(), adesso()))
            record_id = con.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        dopo = dict(con.execute("SELECT * FROM norme WHERE id=?", (record_id,)).fetchone())
        registra_audit(con, utente=utente, azione="norma_modificata" if esistente else "norma_creata",
                       entita="norme", entita_id=record_id,
                       prima=dict(esistente) if esistente else None, dopo=dopo)
    return dopo


# ------------------------------------------------------------ indicatori -----

def _indicatori_con_stato(sistema: str = "") -> list[dict]:
    sql, par = "SELECT * FROM indicatori", []
    if sistema:
        sql += " WHERE sistema=?"
        par.append(sistema)
    uscita = []
    for ind in righe(sql + " ORDER BY sistema, codice", par):
        misure = righe("SELECT * FROM misure WHERE indicatore_id=? ORDER BY periodo DESC LIMIT 12",
                       (ind["id"],))
        ultima = misure[0] if misure else None
        uscita.append({**ind,
                       "ultima_misura": ultima["valore"] if ultima else None,
                       "ultimo_periodo": ultima["periodo"] if ultima else None,
                       "stato_soglia": stato_indicatore(ultima["valore"] if ultima else None, ind),
                       "serie": list(reversed(misure))})
    return uscita


@app.get("/api/indicatori")
def elenco_indicatori(sistema: str = "") -> list[dict]:
    return _indicatori_con_stato(sistema)


@app.post("/api/indicatori")
def salva_indicatore(corpo: dict = Body(...)) -> dict:
    utente = (corpo.pop("utente", "") or "").strip()
    if not utente:
        raise HTTPException(400, "Indicare l'operatore.")
    campi = {k: v for k, v in corpo.items() if k in tools.CAMPI_INDICATORE}
    if not campi.get("codice") or not campi.get("sistema"):
        raise HTTPException(400, "Codice e sistema obbligatori.")
    with connessione() as con:
        esistente = con.execute("SELECT * FROM indicatori WHERE lower(codice)=lower(?) AND sistema=?",
                                (campi["codice"], campi["sistema"])).fetchone()
        if esistente:
            con.execute(f"UPDATE indicatori SET {', '.join(f'{k}=?' for k in campi)}, aggiornato_il=? WHERE id=?",
                        (*campi.values(), adesso(), esistente["id"]))
            record_id = esistente["id"]
        else:
            campi.setdefault("descrizione", campi["codice"])
            colonne = list(campi) + ["creato_il", "aggiornato_il"]
            con.execute(f"INSERT INTO indicatori ({','.join(colonne)}) VALUES ({','.join('?' * len(colonne))})",
                        (*campi.values(), adesso(), adesso()))
            record_id = con.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        dopo = dict(con.execute("SELECT * FROM indicatori WHERE id=?", (record_id,)).fetchone())
        registra_audit(con, utente=utente,
                       azione="indicatore_modificato" if esistente else "indicatore_creato",
                       entita="indicatori", entita_id=record_id,
                       prima=dict(esistente) if esistente else None, dopo=dopo)
    return dopo


@app.post("/api/indicatori/{indicatore_id}/misure")
def salva_misura(indicatore_id: int, corpo: dict = Body(...)) -> dict:
    utente = (corpo.get("utente") or "").strip()
    if not utente:
        raise HTTPException(400, "Indicare l'operatore.")
    if corpo.get("periodo") in (None, "") or corpo.get("valore") in (None, ""):
        raise HTTPException(400, "Periodo e valore obbligatori.")
    with connessione() as con:
        ind = con.execute("SELECT * FROM indicatori WHERE id=?", (indicatore_id,)).fetchone()
        if not ind:
            raise HTTPException(404, "Indicatore inesistente.")
        prima = con.execute("SELECT * FROM misure WHERE indicatore_id=? AND periodo=?",
                            (indicatore_id, corpo["periodo"])).fetchone()
        con.execute(
            """INSERT INTO misure (indicatore_id, periodo, valore, fonte, note, validato_ot,
                                   inserito_da, inserito_il)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(indicatore_id, periodo) DO UPDATE SET
                   valore=excluded.valore, fonte=excluded.fonte, note=excluded.note,
                   validato_ot=excluded.validato_ot, inserito_da=excluded.inserito_da,
                   inserito_il=excluded.inserito_il""",
            (indicatore_id, corpo["periodo"], float(corpo["valore"]), corpo.get("fonte"),
             corpo.get("note"), 1 if corpo.get("validato_ot") else 0, utente, adesso()))
        dopo = dict(con.execute("SELECT * FROM misure WHERE indicatore_id=? AND periodo=?",
                                (indicatore_id, corpo["periodo"])).fetchone())
        registra_audit(con, utente=utente, azione="misura_registrata", entita="misure",
                       entita_id=dopo["id"], prima=dict(prima) if prima else None, dopo=dopo,
                       note=f"{ind['codice']} ({ind['sistema']}) {corpo['periodo']}")
    return dopo


# ------------------------------------------------------------ documenti ------

@app.get("/api/documenti")
def elenco_documenti() -> list[dict]:
    return righe("SELECT id, codice, titolo, tipo, sistema, revisione, stato, n_chunk, "
                 "indicizzato_il, percorso FROM documenti ORDER BY sistema, codice")


@app.post("/api/indicizza")
def indicizza(corpo: dict = Body(default={})) -> dict:
    esiti = indicizza_cartella(utente=corpo.get("utente") or "operatore", forza=bool(corpo.get("forza")))
    return {"esiti": esiti, "totale": len(esiti)}


@app.post("/api/documenti/carica")
async def carica(file: UploadFile = File(...), utente: str = Form("operatore")) -> dict:
    if SOLA_LETTURA:
        raise HTTPException(403, "Modalità sola lettura: SGS Live non scrive nelle cartelle "
                                 "sorgente. Depositare il file dalla condivisione e reindicizzare.")
    nome = Path(file.filename or "documento").name
    if Path(nome).suffix.lower() not in ESTENSIONI:
        raise HTTPException(400, f"Estensione non gestita. Ammesse: {', '.join(sorted(ESTENSIONI))}")
    CARTELLA_DOCUMENTI.mkdir(parents=True, exist_ok=True)
    destinazione = CARTELLA_DOCUMENTI / nome
    with destinazione.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    from .ingest import indicizza_file
    return indicizza_file(destinazione, utente=utente, forza=True)


@app.get("/api/documenti/{documento_id}/file")
def scarica(documento_id: int) -> FileResponse:
    doc = riga("SELECT percorso, codice FROM documenti WHERE id=?", (documento_id,))
    if not doc or not Path(doc["percorso"]).exists():
        raise HTTPException(404, "File non disponibile.")
    return FileResponse(doc["percorso"], filename=Path(doc["percorso"]).name)


# ----------------------------------------------------------------- audit -----

@app.get("/api/audit")
def audit(limite: int = 100) -> list[dict]:
    return righe("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limite,))


@app.get("/api/esporta/{entita}.csv")
def esporta(entita: str) -> StreamingResponse:
    if entita not in {"norme", "indicatori", "misure", "audit_log", "proposte"}:
        raise HTTPException(404, "Entità non esportabile.")
    if entita == "misure":
        dati = righe("""SELECT i.codice, i.sistema, i.descrizione, m.periodo, m.valore,
                               i.unita_misura, i.soglia_allarme, i.soglia_intervento,
                               m.fonte, m.note, m.validato_ot, m.inserito_da, m.inserito_il
                        FROM misure m JOIN indicatori i ON i.id=m.indicatore_id
                        ORDER BY i.sistema, i.codice, m.periodo""")
    else:
        dati = righe(f"SELECT * FROM {entita}")
    buffer = io.StringIO()
    if dati:
        scrittore = csv.DictWriter(buffer, fieldnames=list(dati[0]), delimiter=";")
        scrittore.writeheader()
        scrittore.writerows(dati)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue().encode("utf-8-sig")]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{entita}.csv"'})


app.mount("/static", StaticFiles(directory=CARTELLA_WEB), name="static")
