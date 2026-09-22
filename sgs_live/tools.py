"""Strumenti esposti all'assistente: lettura libera, scrittura solo per proposta.

Nessuno strumento scrive direttamente su registri o indicatori. Le richieste di
modifica producono una riga in `proposte` (stato 'in_attesa'); la scrittura
avviene solo in `applica_proposta`, invocata dalla conferma esplicita di un
operatore identificato, con registrazione in `audit_log`.
"""
from __future__ import annotations

import json
from typing import Any

from .db import adesso, connessione, registra_audit, righe, stato_indicatore
from .retrieval import cerca, estratto

CAMPI_NORMA = [
    "riferimento", "titolo", "ente", "tipo_atto", "data_pubblicazione", "data_entrata_vigore",
    "sistemi", "ambito", "stato", "sintesi_applicabilita", "valutazione_impatto",
    "azioni_conseguenti", "responsabile", "scadenza", "documenti_sgs_impattati", "note",
]
CAMPI_INDICATORE = [
    "codice", "sistema", "descrizione", "unita_misura", "tipo", "verso", "soglia_allarme",
    "soglia_intervento", "soglia_accettabilita", "id_ep", "responsabile", "periodicita", "note",
]

STRUMENTI: list[dict[str, Any]] = [
    {
        "name": "cerca_nei_documenti",
        "description": (
            "Cerca passaggi pertinenti nei documenti SGS indicizzati (Manuale, Procedure, "
            "Istruzioni Operative, Registri). Da usare SEMPRE prima di rispondere su contenuti "
            "documentali: e' l'unica fonte ammessa per citare il SGS."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domanda": {"type": "string", "description": "Concetti da cercare, in italiano."},
                "sistema": {"type": "string", "enum": ["TGV", "MET", "FGC", "FPG", "FIL"],
                             "description": "Filtro per sistema; omettere se non richiesto."},
                "tipo_documento": {"type": "string",
                                    "description": "Es. Procedura, Manuale, Registro, Istruzione Operativa."},
                "codice_documento": {"type": "string", "description": "Es. TGV_PRC_11."},
                "massimo": {"type": "integer", "description": "Numero di passaggi (default 6, max 12)."},
            },
            "required": ["domanda"],
        },
    },
    {
        "name": "leggi_estratto",
        "description": ("Restituisce il testo integrale di un passaggio gia' individuato con "
                         "cerca_nei_documenti, con il contesto circostante. Usare quando serve "
                         "riportare l'estratto letterale."),
        "input_schema": {
            "type": "object",
            "properties": {
                "chunk_id": {"type": "integer"},
                "contesto": {"type": "integer", "description": "Blocchi adiacenti (default 1, max 3)."},
            },
            "required": ["chunk_id"],
        },
    },
    {
        "name": "elenca_documenti",
        "description": "Elenca i documenti SGS indicizzati con codice, titolo, tipo, revisione.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sistema": {"type": "string", "enum": ["TGV", "MET", "FGC", "FPG", "FIL"]},
                "tipo": {"type": "string"},
            },
        },
    },
    {
        "name": "consulta_registro_norme",
        "description": ("Interroga il Registro normative di riferimento (TGV_MSGS_RGS_01): "
                         "riferimenti, applicabilita', stato, azioni e scadenze."),
        "input_schema": {
            "type": "object",
            "properties": {
                "testo": {"type": "string", "description": "Testo libero su riferimento/titolo/ambito."},
                "sistema": {"type": "string", "enum": ["TGV", "MET", "FGC", "FPG", "FIL"]},
                "stato": {"type": "string", "enum": ["vigente", "abrogata", "in_recepimento", "monitoraggio"]},
                "solo_scadenze_aperte": {"type": "boolean"},
            },
        },
    },
    {
        "name": "consulta_indicatori",
        "description": ("Interroga il Registro Indicatori Prestazionali di Sicurezza "
                         "(TGV_PRC_06_RGS_02) e le misure registrate, con lo stato rispetto "
                         "alle soglie di Allarme e Intervento (TGV_PRC_11)."),
        "input_schema": {
            "type": "object",
            "properties": {
                "codice": {"type": "string", "description": "Es. IPS01."},
                "sistema": {"type": "string", "enum": ["TGV", "MET", "FGC", "FPG", "FIL"]},
                "periodo": {"type": "string", "description": "Es. 2026-Q1."},
                "solo_fuori_soglia": {"type": "boolean"},
            },
        },
    },
    {
        "name": "proponi_norma",
        "description": ("Propone l'inserimento o l'aggiornamento di una voce del Registro "
                         "normative. NON scrive: crea una proposta che l'operatore deve "
                         "confermare nella dashboard. Compilare solo i campi da impostare."),
        "input_schema": {
            "type": "object",
            "properties": {
                "azione": {"type": "string", "enum": ["crea", "aggiorna"]},
                "riferimento": {"type": "string",
                                 "description": "Identificativo dell'atto, es. 'D.Lgs. 50/2019'."},
                "titolo": {"type": "string"},
                "ente": {"type": "string", "description": "Es. ANSFISA, MIT, UE, CEI."},
                "tipo_atto": {"type": "string",
                               "description": "Es. Decreto legislativo, Regolamento UE, Linea guida, Norma tecnica."},
                "data_pubblicazione": {"type": "string", "description": "AAAA-MM-GG."},
                "data_entrata_vigore": {"type": "string", "description": "AAAA-MM-GG."},
                "sistemi": {"type": "string", "description": "Sistemi applicabili, es. 'MET, FPG'."},
                "ambito": {"type": "string"},
                "stato": {"type": "string", "enum": ["vigente", "abrogata", "in_recepimento", "monitoraggio"]},
                "sintesi_applicabilita": {"type": "string"},
                "valutazione_impatto": {"type": "string"},
                "azioni_conseguenti": {"type": "string"},
                "responsabile": {"type": "string", "description": "Es. RSGS, RTEM, RFAF."},
                "scadenza": {"type": "string", "description": "AAAA-MM-GG."},
                "documenti_sgs_impattati": {"type": "string", "description": "Es. 'TGV_PRC_11, TGV_MSGS'."},
                "note": {"type": "string"},
                "motivazione": {"type": "string",
                                 "description": "Perche' la modifica e' proposta e su quale fonte si basa."},
            },
            "required": ["azione", "riferimento", "motivazione"],
        },
    },
    {
        "name": "proponi_indicatore",
        "description": ("Propone l'inserimento o l'aggiornamento di un IPS nel registro "
                         "indicatori. NON scrive: richiede conferma dell'operatore."),
        "input_schema": {
            "type": "object",
            "properties": {
                "azione": {"type": "string", "enum": ["crea", "aggiorna"]},
                "codice": {"type": "string", "description": "Es. IPS01."},
                "sistema": {"type": "string", "enum": ["TGV", "MET", "FGC", "FPG", "FIL"]},
                "descrizione": {"type": "string"},
                "unita_misura": {"type": "string",
                                  "description": "Spesso un rapporto, es. 'n. dec. chiuse in ritardo / n. dec. chiuse'."},
                "tipo": {"type": "string", "enum": ["reattivo", "proattivo"]},
                "verso": {"type": "string", "enum": ["min", "max"],
                           "description": "'min' se valori bassi sono desiderabili, 'max' se alti."},
                "soglia_allarme": {"type": "number"},
                "soglia_intervento": {"type": "number"},
                "soglia_accettabilita": {"type": "string"},
                "id_ep": {"type": "string", "description": "ID eventi pericolosi correlati nell'Hazard Log."},
                "responsabile": {"type": "string"},
                "periodicita": {"type": "string"},
                "note": {"type": "string"},
                "motivazione": {"type": "string"},
            },
            "required": ["azione", "codice", "sistema", "motivazione"],
        },
    },
    {
        "name": "proponi_misura",
        "description": ("Propone la registrazione del valore di un IPS per un periodo "
                         "(raccolta trimestrale a cura del RSGS). NON scrive: richiede conferma."),
        "input_schema": {
            "type": "object",
            "properties": {
                "codice": {"type": "string", "description": "Codice IPS, es. IPS03."},
                "sistema": {"type": "string", "enum": ["TGV", "MET", "FGC", "FPG", "FIL"]},
                "periodo": {"type": "string", "description": "Es. 2026-Q1 oppure 2026."},
                "valore": {"type": "number"},
                "fonte": {"type": "string", "description": "Da chi/da quale dato proviene il valore."},
                "note": {"type": "string"},
                "motivazione": {"type": "string"},
            },
            "required": ["codice", "periodo", "valore", "motivazione"],
        },
    },
]

NOMI_SCRITTURA = {"proponi_norma", "proponi_indicatore", "proponi_misura"}


# ---------------------------------------------------------------- lettura ----

def _intestazione(r: dict) -> str:
    """Riferimento citabile di un passaggio: codice, titolo, revisione, pagina, sezione."""
    parti = [f"{r['codice']} - {r['titolo']}"]
    if r.get("revisione"):
        parti.append(f"rev. {r['revisione']}")
    if r.get("pagina"):
        parti.append(f"pag. {r['pagina']}")
    if r.get("sezione"):
        parti.append(f"sez. {r['sezione']}")
    return ", ".join(parti)


def _cerca(par: dict) -> tuple[str, list[dict]]:
    risultati = cerca(
        par["domanda"], sistema=par.get("sistema"), tipo_documento=par.get("tipo_documento"),
        codice_documento=par.get("codice_documento"), massimo=min(int(par.get("massimo", 6)), 12),
    )
    if not risultati:
        return ("Nessun passaggio trovato nei documenti indicizzati. Non inventare il contenuto: "
                "segnalare all'operatore che il documento potrebbe non essere caricato.", [])
    voci = []
    for r in risultati:
        voci.append(f"[chunk_id={r['chunk_id']}] {_intestazione(r)}\n{r['testo'][:1600]}")
    citazioni = [
        {"chunk_id": r["chunk_id"], "codice": r["codice"], "titolo": r["titolo"],
         "pagina": r["pagina"], "sezione": r["sezione"], "revisione": r["revisione"],
         "evidenza": r["evidenza"]}
        for r in risultati
    ]
    return "\n\n---\n\n".join(voci), citazioni


def _leggi_estratto(par: dict) -> tuple[str, list[dict]]:
    dato = estratto(int(par["chunk_id"]), contesto=min(int(par.get("contesto", 1)), 3))
    if not dato:
        return "Passaggio non trovato.", []
    citazione = {k: dato[k] for k in ("chunk_id", "codice", "titolo", "pagina", "sezione", "revisione")}
    citazione["evidenza"] = dato["testo"][:300]
    return f"{_intestazione(dato)}\n\n{dato['testo']}", [citazione]


def _elenca_documenti(par: dict) -> tuple[str, list[dict]]:
    sql = "SELECT codice, titolo, tipo, sistema, revisione, n_chunk FROM documenti WHERE 1=1"
    p: list[Any] = []
    if par.get("sistema"):
        sql += " AND sistema=?"
        p.append(par["sistema"])
    if par.get("tipo"):
        sql += " AND tipo=?"
        p.append(par["tipo"])
    elenco = righe(sql + " ORDER BY sistema, codice", p)
    if not elenco:
        return "Nessun documento indicizzato. Caricare i file nella cartella documenti e avviare l'indicizzazione.", []
    return json.dumps(elenco, ensure_ascii=False, indent=1), []


def _consulta_norme(par: dict) -> tuple[str, list[dict]]:
    sql = "SELECT * FROM norme WHERE 1=1"
    p: list[Any] = []
    if par.get("testo"):
        sql += (" AND (riferimento LIKE ? OR titolo LIKE ? OR ambito LIKE ?"
                " OR sintesi_applicabilita LIKE ? OR documenti_sgs_impattati LIKE ?)")
        p += [f"%{par['testo']}%"] * 5
    if par.get("sistema"):
        sql += " AND sistemi LIKE ?"
        p.append(f"%{par['sistema']}%")
    if par.get("stato"):
        sql += " AND stato=?"
        p.append(par["stato"])
    if par.get("solo_scadenze_aperte"):
        sql += " AND scadenza IS NOT NULL AND scadenza <> '' AND stato <> 'abrogata'"
    elenco = righe(sql + " ORDER BY riferimento", p)
    return (json.dumps(elenco, ensure_ascii=False, indent=1) if elenco
            else "Nessuna voce corrispondente nel registro normative."), []


def _consulta_indicatori(par: dict) -> tuple[str, list[dict]]:
    sql = "SELECT * FROM indicatori WHERE 1=1"
    p: list[Any] = []
    if par.get("codice"):
        sql += " AND codice LIKE ?"
        p.append(f"%{par['codice']}%")
    if par.get("sistema"):
        sql += " AND sistema=?"
        p.append(par["sistema"])
    elenco = righe(sql + " ORDER BY sistema, codice", p)

    uscita = []
    for ind in elenco:
        sql_m = "SELECT periodo, valore, fonte, note, validato_ot, inserito_da, inserito_il FROM misure WHERE indicatore_id=?"
        pm: list[Any] = [ind["id"]]
        if par.get("periodo"):
            sql_m += " AND periodo=?"
            pm.append(par["periodo"])
        misure = righe(sql_m + " ORDER BY periodo DESC LIMIT 8", pm)
        ultima = misure[0]["valore"] if misure else None
        stato = stato_indicatore(ultima, ind)
        if par.get("solo_fuori_soglia") and stato not in ("allarme", "intervento"):
            continue
        uscita.append({**ind, "ultima_misura": ultima, "stato_soglia": stato, "misure": misure})
    return (json.dumps(uscita, ensure_ascii=False, indent=1) if uscita
            else "Nessun indicatore corrispondente."), []


# --------------------------------------------------------------- proposte ----

def _anteprima_differenze(entita: str, chiave: dict, campi: dict) -> tuple[dict | None, dict]:
    """Stato attuale del record (se esiste) e campi che verrebbero modificati."""
    attuale = None
    if entita == "norme":
        attuale = righe("SELECT * FROM norme WHERE lower(riferimento)=lower(?)",
                        [chiave["riferimento"]])
    elif entita == "indicatori":
        attuale = righe("SELECT * FROM indicatori WHERE lower(codice)=lower(?) AND sistema=?",
                        [chiave["codice"], chiave.get("sistema", "TGV")])
    elif entita == "misure":
        attuale = righe(
            """SELECT m.* FROM misure m JOIN indicatori i ON i.id=m.indicatore_id
               WHERE lower(i.codice)=lower(?) AND i.sistema=? AND m.periodo=?""",
            [chiave["codice"], chiave.get("sistema", "TGV"), chiave["periodo"]])
    attuale = attuale[0] if attuale else None
    differenze = {k: {"prima": (attuale or {}).get(k), "dopo": v} for k, v in campi.items()
                  if (attuale or {}).get(k) != v}
    return attuale, differenze


def _crea_proposta(*, strumento: str, entita: str, riepilogo: str, motivazione: str,
                   payload: dict, anteprima: dict, contesto: dict) -> tuple[str, dict]:
    with connessione() as con:
        cur = con.execute(
            """INSERT INTO proposte (creata_il, sessione, utente, strumento, entita, riepilogo,
                                     motivazione, payload, anteprima, stato)
               VALUES (?,?,?,?,?,?,?,?,?,'in_attesa')""",
            (adesso(), contesto.get("sessione"), contesto.get("utente"), strumento, entita,
             riepilogo, motivazione, json.dumps(payload, ensure_ascii=False),
             json.dumps(anteprima, ensure_ascii=False)),
        )
        pid = cur.lastrowid
        registra_audit(con, utente=contesto.get("utente", "sconosciuto"), azione="proposta_creata",
                       entita=entita, entita_id=pid, dopo=payload, origine="assistente",
                       proposta_id=pid, note=riepilogo)
    return (
        f"Proposta n. {pid} registrata in stato 'in attesa'. NESSUNA modifica e' stata scritta: "
        f"l'operatore deve confermarla nel pannello 'Modifiche da confermare'. "
        f"Riepilogo: {riepilogo}",
        {"id": pid, "strumento": strumento, "entita": entita, "riepilogo": riepilogo,
         "motivazione": motivazione, "anteprima": anteprima, "stato": "in_attesa"},
    )


def _proponi_norma(par: dict, contesto: dict) -> tuple[str, dict]:
    campi = {k: v for k, v in par.items() if k in CAMPI_NORMA and v not in (None, "")}
    campi.setdefault("riferimento", par["riferimento"])
    attuale, differenze = _anteprima_differenze("norme", {"riferimento": par["riferimento"]}, campi)
    azione = par["azione"]
    if azione == "aggiorna" and not attuale:
        return (f"Nessuna voce '{par['riferimento']}' nel registro normative: usare azione='crea' "
                f"oppure verificare il riferimento."), {}
    if azione == "crea" and attuale:
        azione = "aggiorna"
    return _crea_proposta(
        strumento="proponi_norma", entita="norme",
        riepilogo=f"{'Aggiornamento' if azione == 'aggiorna' else 'Inserimento'} norma "
                   f"{par['riferimento']} nel Registro normative (TGV_MSGS_RGS_01)",
        motivazione=par["motivazione"],
        payload={"azione": azione, "chiave": {"riferimento": par["riferimento"]}, "campi": campi},
        anteprima={"esistente": attuale, "differenze": differenze}, contesto=contesto)


def _proponi_indicatore(par: dict, contesto: dict) -> tuple[str, dict]:
    campi = {k: v for k, v in par.items() if k in CAMPI_INDICATORE and v not in (None, "")}
    chiave = {"codice": par["codice"], "sistema": par["sistema"]}
    campi.update(chiave)
    attuale, differenze = _anteprima_differenze("indicatori", chiave, campi)
    azione = par["azione"]
    if azione == "aggiorna" and not attuale:
        return f"Nessun indicatore {par['codice']} per il sistema {par['sistema']}: usare azione='crea'.", {}
    if azione == "crea" and attuale:
        azione = "aggiorna"
    if azione == "crea" and not campi.get("descrizione"):
        return "Per creare un IPS serve almeno la descrizione. Chiedere il dato all'operatore.", {}
    return _crea_proposta(
        strumento="proponi_indicatore", entita="indicatori",
        riepilogo=f"{'Aggiornamento' if azione == 'aggiorna' else 'Inserimento'} indicatore "
                   f"{par['codice']} ({par['sistema']}) nel registro IPS",
        motivazione=par["motivazione"],
        payload={"azione": azione, "chiave": chiave, "campi": campi},
        anteprima={"esistente": attuale, "differenze": differenze}, contesto=contesto)


def _proponi_misura(par: dict, contesto: dict) -> tuple[str, dict]:
    sistema = par.get("sistema")
    candidati = righe("SELECT * FROM indicatori WHERE lower(codice)=lower(?)" +
                      (" AND sistema=?" if sistema else ""),
                      [par["codice"]] + ([sistema] if sistema else []))
    if not candidati:
        return (f"Indicatore {par['codice']} non presente nel registro"
                f"{f' per il sistema {sistema}' if sistema else ''}. "
                f"Proporre prima l'indicatore con proponi_indicatore."), {}
    if len(candidati) > 1:
        sistemi = ", ".join(c["sistema"] for c in candidati)
        return f"{par['codice']} esiste per piu' sistemi ({sistemi}): specificare il parametro 'sistema'.", {}

    ind = candidati[0]
    chiave = {"codice": ind["codice"], "sistema": ind["sistema"], "periodo": par["periodo"]}
    campi = {"valore": float(par["valore"]), "fonte": par.get("fonte"), "note": par.get("note")}
    attuale, differenze = _anteprima_differenze("misure", chiave, {k: v for k, v in campi.items() if v is not None})
    nuovo_stato = stato_indicatore(float(par["valore"]), ind)
    return _crea_proposta(
        strumento="proponi_misura", entita="misure",
        riepilogo=f"Registrazione misura {ind['codice']} ({ind['sistema']}) periodo "
                   f"{par['periodo']}: {par['valore']} {ind['unita_misura'] or ''} → stato «{nuovo_stato}»",
        motivazione=par["motivazione"],
        payload={"azione": "sostituisci", "chiave": chiave, "campi": campi},
        anteprima={"esistente": attuale,
                   "differenze": differenze,
                   "stato_soglia": nuovo_stato,
                   "soglia_allarme": ind["soglia_allarme"],
                   "soglia_intervento": ind["soglia_intervento"]},
        contesto=contesto)


# -------------------------------------------------------------- dispatcher ---

def esegui(nome: str, parametri: dict, contesto: dict) -> dict:
    """Esegue uno strumento. Restituisce testo per il modello + metadati per l'interfaccia."""
    try:
        if nome == "cerca_nei_documenti":
            testo, citazioni = _cerca(parametri)
            return {"testo": testo, "citazioni": citazioni}
        if nome == "leggi_estratto":
            testo, citazioni = _leggi_estratto(parametri)
            return {"testo": testo, "citazioni": citazioni}
        if nome == "elenca_documenti":
            testo, _ = _elenca_documenti(parametri)
            return {"testo": testo}
        if nome == "consulta_registro_norme":
            testo, _ = _consulta_norme(parametri)
            return {"testo": testo}
        if nome == "consulta_indicatori":
            testo, _ = _consulta_indicatori(parametri)
            return {"testo": testo}
        if nome == "proponi_norma":
            testo, proposta = _proponi_norma(parametri, contesto)
            return {"testo": testo, "proposta": proposta or None}
        if nome == "proponi_indicatore":
            testo, proposta = _proponi_indicatore(parametri, contesto)
            return {"testo": testo, "proposta": proposta or None}
        if nome == "proponi_misura":
            testo, proposta = _proponi_misura(parametri, contesto)
            return {"testo": testo, "proposta": proposta or None}
        return {"testo": f"Strumento sconosciuto: {nome}", "errore": True}
    except Exception as exc:
        return {"testo": f"Errore nell'esecuzione di {nome}: {exc}", "errore": True}


# ------------------------------------------------------- applica / rifiuta ---

def applica_proposta(proposta_id: int, utente: str) -> dict:
    """Scrive la modifica proposta. Unico punto in cui i registri vengono aggiornati."""
    with connessione() as con:
        p = con.execute("SELECT * FROM proposte WHERE id=?", (proposta_id,)).fetchone()
        if not p:
            raise ValueError("Proposta inesistente.")
        if p["stato"] != "in_attesa":
            raise ValueError(f"Proposta gia' {p['stato']}.")

        payload = json.loads(p["payload"])
        chiave, campi, azione = payload["chiave"], payload["campi"], payload["azione"]
        entita, prima, dopo = p["entita"], None, None

        if entita == "norme":
            esistente = con.execute("SELECT * FROM norme WHERE lower(riferimento)=lower(?)",
                                    (chiave["riferimento"],)).fetchone()
            if esistente:
                prima = dict(esistente)
                assegnazioni = ", ".join(f"{k}=?" for k in campi)
                con.execute(f"UPDATE norme SET {assegnazioni}, aggiornato_il=? WHERE id=?",
                            (*campi.values(), adesso(), esistente["id"]))
                record_id = esistente["id"]
            else:
                campi.setdefault("titolo", chiave["riferimento"])
                colonne = list(campi) + ["creato_il", "aggiornato_il"]
                con.execute(
                    f"INSERT INTO norme ({','.join(colonne)}) VALUES ({','.join('?' * len(colonne))})",
                    (*campi.values(), adesso(), adesso()))
                record_id = con.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
            dopo = dict(con.execute("SELECT * FROM norme WHERE id=?", (record_id,)).fetchone())

        elif entita == "indicatori":
            esistente = con.execute("SELECT * FROM indicatori WHERE lower(codice)=lower(?) AND sistema=?",
                                    (chiave["codice"], chiave["sistema"])).fetchone()
            if esistente:
                prima = dict(esistente)
                assegnazioni = ", ".join(f"{k}=?" for k in campi)
                con.execute(f"UPDATE indicatori SET {assegnazioni}, aggiornato_il=? WHERE id=?",
                            (*campi.values(), adesso(), esistente["id"]))
                record_id = esistente["id"]
            else:
                campi.setdefault("descrizione", chiave["codice"])
                colonne = list(campi) + ["creato_il", "aggiornato_il"]
                con.execute(
                    f"INSERT INTO indicatori ({','.join(colonne)}) VALUES ({','.join('?' * len(colonne))})",
                    (*campi.values(), adesso(), adesso()))
                record_id = con.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
            dopo = dict(con.execute("SELECT * FROM indicatori WHERE id=?", (record_id,)).fetchone())

        elif entita == "misure":
            ind = con.execute("SELECT * FROM indicatori WHERE lower(codice)=lower(?) AND sistema=?",
                              (chiave["codice"], chiave["sistema"])).fetchone()
            if not ind:
                raise ValueError("Indicatore non piu' presente nel registro.")
            esistente = con.execute("SELECT * FROM misure WHERE indicatore_id=? AND periodo=?",
                                    (ind["id"], chiave["periodo"])).fetchone()
            prima = dict(esistente) if esistente else None
            con.execute(
                """INSERT INTO misure (indicatore_id, periodo, valore, fonte, note, inserito_da, inserito_il)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(indicatore_id, periodo) DO UPDATE SET
                       valore=excluded.valore, fonte=excluded.fonte, note=excluded.note,
                       inserito_da=excluded.inserito_da, inserito_il=excluded.inserito_il,
                       validato_ot=0""",
                (ind["id"], chiave["periodo"], campi["valore"], campi.get("fonte"),
                 campi.get("note"), utente, adesso()))
            record_id = con.execute("SELECT id FROM misure WHERE indicatore_id=? AND periodo=?",
                                    (ind["id"], chiave["periodo"])).fetchone()["id"]
            dopo = dict(con.execute("SELECT * FROM misure WHERE id=?", (record_id,)).fetchone())
        else:
            raise ValueError(f"Entita' non gestita: {entita}")

        con.execute("UPDATE proposte SET stato='confermata', decisa_il=?, decisa_da=?, esito=? WHERE id=?",
                    (adesso(), utente, f"{entita} id={record_id}", proposta_id))
        registra_audit(con, utente=utente, azione=f"{entita}_{azione}", entita=entita,
                       entita_id=record_id, prima=prima, dopo=dopo, origine="conferma_operatore",
                       proposta_id=proposta_id, note=p["riepilogo"])
    return {"proposta": proposta_id, "entita": entita, "id": record_id}


def rifiuta_proposta(proposta_id: int, utente: str, motivo: str = "") -> dict:
    with connessione() as con:
        p = con.execute("SELECT * FROM proposte WHERE id=?", (proposta_id,)).fetchone()
        if not p:
            raise ValueError("Proposta inesistente.")
        if p["stato"] != "in_attesa":
            raise ValueError(f"Proposta gia' {p['stato']}.")
        con.execute("UPDATE proposte SET stato='rifiutata', decisa_il=?, decisa_da=?, esito=? WHERE id=?",
                    (adesso(), utente, motivo, proposta_id))
        registra_audit(con, utente=utente, azione="proposta_rifiutata", entita=p["entita"],
                       entita_id=proposta_id, origine="conferma_operatore", proposta_id=proposta_id,
                       note=motivo or p["riepilogo"])
    return {"proposta": proposta_id, "stato": "rifiutata"}
