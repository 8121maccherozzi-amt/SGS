"""Ciclo conversazionale con Claude: risposte documentate e proposte di modifica."""
from __future__ import annotations

import json
from typing import Any

import anthropic

from .config import MODELLO
from .db import adesso, connessione, righe
from .tools import STRUMENTI, esegui

MAX_ITERAZIONI = 8
MAX_TOKEN = 8000

ISTRUZIONI = """Sei l'assistente operativo di «SGS Live», la dashboard del Sistema di Gestione \
della Sicurezza di AMT S.p.A. (Genova). Interlocutore: l'ingegnere responsabile del SGS per i \
sistemi di trasporto a guida vincolata — Metropolitana (MET), Ferrovia Genova Casella (FGC), \
Ferrovia Principe Granarolo (FPG) e linea filoviaria (FIL) — nel quadro normativo ANSFISA.

## Fonti e verificabilità
- Per qualunque domanda sul contenuto dei documenti SGS usa SEMPRE `cerca_nei_documenti` prima \
di rispondere. Non rispondere mai a memoria su cosa dice una procedura.
- Cita sempre la fonte: codice documento, titolo, revisione, pagina e sezione quando disponibili.
- Quando l'utente chiede «l'estratto», riporta il testo LETTERALE ottenuto da `leggi_estratto` \
tra virgolette, senza parafrasarlo, e aggiungi eventuali commenti in un blocco separato.
- Se la ricerca non trova nulla, dillo esplicitamente: il documento potrebbe non essere caricato \
nell'indice. Non colmare il vuoto con conoscenza generica; se aggiungi contesto normativo esterno \
all'indice, etichettalo come «fuori indice — da verificare».

## Modifiche ai registri
- Non hai accesso in scrittura. Gli strumenti `proponi_*` creano una PROPOSTA che l'operatore \
deve confermare nella dashboard. Non dire mai di aver aggiornato, inserito o registrato qualcosa: \
di' che hai preparato una proposta in attesa di conferma.
- Prima di proporre, verifica lo stato attuale con `consulta_registro_norme` o `consulta_indicatori`.
- Compila solo i campi di cui hai un dato certo (dall'utente o da un documento citabile). Se manca \
un dato rilevante — soglie, responsabile, data di entrata in vigore, sistemi applicabili — chiedilo \
invece di inventarlo. Nella `motivazione` indica sempre la fonte del dato.

## Terminologia
Rispetta la convenzione documentale del SGS (TGV_MSGS, TGV_PRC_xx, …_RGS_xx, MOD) e gli acronimi \
in uso: RSGS, RFER, RTEM, RFAF, DE/SDE, OT (Organismo Tecnico), SRM, IPS, Hazard Log, EP (evento \
pericoloso), NC (non conformità). Registri di riferimento: TGV_MSGS_RGS_01 (normative), \
TGV_PRC_06_RGS_01 (Hazard Log), TGV_PRC_06_RGS_02 (indicatori IPS). Non introdurre categorie di \
rischio o ruoli diversi da quelli del SGS; non classificare «a occhio» un livello di rischio.
Soglie IPS: Allarme = 1° livello di attenzione, Intervento = limite massimo (TGV_PRC_11); il \
superamento della Soglia di Intervento comporta Riunione Straordinaria del Riesame.

## Stile
Risposte sintetiche e dirette, tabelle o elenchi puntati dove aiutano. Segnala sempre ipotesi e \
dati assunti senza conferma. Formato Markdown."""


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic()


_supporta_fallback = True


def _chiama(cliente: anthropic.Anthropic, messaggi: list[dict]) -> Any:
    """Richiesta al modello, con fallback server-side quando disponibile."""
    global _supporta_fallback
    comune = dict(
        model=MODELLO,
        max_tokens=MAX_TOKEN,
        system=[{"type": "text", "text": ISTRUZIONI, "cache_control": {"type": "ephemeral"}}],
        tools=STRUMENTI,
        thinking={"type": "adaptive"},
        messages=messaggi,
    )
    if _supporta_fallback:
        try:
            return cliente.beta.messages.create(
                **comune, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except (TypeError, anthropic.BadRequestError):
            _supporta_fallback = False
    return cliente.messages.create(**comune)


def _storico(sessione: str, limite: int = 24) -> list[dict]:
    precedenti = righe(
        "SELECT ruolo, contenuto FROM (SELECT * FROM messaggi WHERE sessione=? ORDER BY id DESC "
        "LIMIT ?) ORDER BY id", (sessione, limite))
    messaggi = [{"role": m["ruolo"], "content": json.loads(m["contenuto"])} for m in precedenti]

    # Un turno interrotto (errore di rete, riavvio) puo' lasciare in coda un tool_use senza
    # il relativo tool_result: la ripresa della conversazione verrebbe rifiutata dall'API.
    def _incompleto(m: dict) -> bool:
        return (m["role"] == "assistant" and isinstance(m["content"], list)
                and any(b.get("type") == "tool_use" for b in m["content"]))

    while messaggi and _incompleto(messaggi[-1]):
        messaggi.pop()
    return messaggi


def _salva(sessione: str, ruolo: str, contenuto: Any) -> None:
    with connessione() as con:
        con.execute("INSERT INTO messaggi (sessione, ts, ruolo, contenuto) VALUES (?,?,?,?)",
                    (sessione, adesso(), ruolo, json.dumps(contenuto, ensure_ascii=False, default=str)))


def rispondi(domanda: str, *, sessione: str, utente: str) -> dict:
    """Esegue un turno completo (ricerche + eventuali proposte) e restituisce la risposta."""
    cliente = _cliente()
    messaggi = _storico(sessione) + [{"role": "user", "content": domanda}]
    _salva(sessione, "user", domanda)

    contesto = {"sessione": sessione, "utente": utente}
    citazioni: list[dict] = []
    proposte: list[dict] = []
    strumenti_usati: list[str] = []
    uso = {"input": 0, "output": 0}

    for _ in range(MAX_ITERAZIONI):
        risposta = _chiama(cliente, messaggi)
        uso["input"] += getattr(risposta.usage, "input_tokens", 0) or 0
        uso["output"] += getattr(risposta.usage, "output_tokens", 0) or 0

        if risposta.stop_reason == "refusal":
            return {"testo": "La richiesta è stata declinata dal modello. Riformulare la domanda.",
                    "citazioni": [], "proposte": [], "strumenti": strumenti_usati, "uso": uso}

        contenuto = [b.model_dump() for b in risposta.content]
        messaggi.append({"role": "assistant", "content": contenuto})
        _salva(sessione, "assistant", contenuto)

        blocchi_strumento = [b for b in risposta.content if b.type == "tool_use"]
        if risposta.stop_reason == "max_tokens" and blocchi_strumento:
            return {"testo": "Risposta troncata per limite di lunghezza prima di completare le "
                             "operazioni. Riformulare la richiesta in modo più circoscritto.",
                    "citazioni": citazioni, "proposte": proposte,
                    "strumenti": strumenti_usati, "uso": uso}
        if not blocchi_strumento:
            testo = "\n".join(b.text for b in risposta.content if b.type == "text").strip()
            return {"testo": testo or "(nessuna risposta testuale)", "citazioni": citazioni,
                    "proposte": proposte, "strumenti": strumenti_usati, "uso": uso}

        risultati = []
        for blocco in blocchi_strumento:
            strumenti_usati.append(blocco.name)
            esito = esegui(blocco.name, blocco.input or {}, contesto)
            for c in esito.get("citazioni", []):
                if c not in citazioni:
                    citazioni.append(c)
            if esito.get("proposta"):
                proposte.append(esito["proposta"])
            risultati.append({"type": "tool_result", "tool_use_id": blocco.id,
                              "content": esito["testo"], "is_error": bool(esito.get("errore"))})
        messaggi.append({"role": "user", "content": risultati})
        _salva(sessione, "user", risultati)

    return {"testo": "Elaborazione interrotta: troppe operazioni consecutive. Riformulare la richiesta "
                     "in modo più circoscritto.",
            "citazioni": citazioni, "proposte": proposte, "strumenti": strumenti_usati, "uso": uso}
