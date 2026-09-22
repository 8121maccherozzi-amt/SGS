"""Procedura guidata di prima configurazione: scrive il file .env rispondendo a poche domande."""
from __future__ import annotations

import os
from pathlib import Path

from .config import RADICE

DOMANDE_PERCORSO = (
    "\nDove si trovano i documenti del SGS?\n"
    "  Incolla il percorso della cartella (es. S:\\SGS\\Documentazione oppure\n"
    "  \\\\srv-file\\SGS). Puoi indicarne più di una separandole con «;».\n"
    "  Invio per usare la cartella «documenti» qui dentro.\n> "
)


def _chiedi(testo: str, predefinito: str = "") -> str:
    try:
        risposta = input(testo).strip()
    except (EOFError, KeyboardInterrupt):
        return predefinito
    return risposta or predefinito


def _si_no(testo: str, predefinito: bool) -> bool:
    suggerimento = "S/n" if predefinito else "s/N"
    risposta = _chiedi(f"{testo} [{suggerimento}] ", "").lower()
    if not risposta:
        return predefinito
    return risposta.startswith("s")


def _pulisci_percorso(valore: str) -> str:
    """Toglie virgolette e spazi: Windows li aggiunge quando si trascina una cartella."""
    return valore.strip().strip('"').strip("'").rstrip("\\/") or valore.strip()


def esegui(percorso_env: Path | None = None, *, forza: bool = False) -> Path:
    percorso_env = Path(percorso_env or RADICE / ".env")
    if percorso_env.exists() and not forza:
        print(f"Configurazione già presente: {percorso_env}")
        if not _si_no("Vuoi rifarla da capo?", False):
            return percorso_env

    print("\n" + "=" * 68)
    print("  SGS Live — configurazione iniziale")
    print("=" * 68)

    cartelle = _chiedi(DOMANDE_PERCORSO, str(RADICE / "documenti"))
    cartelle = ";".join(_pulisci_percorso(c) for c in cartelle.split(";") if c.strip())

    for cartella in cartelle.split(";"):
        if not Path(os.path.expandvars(os.path.expanduser(cartella))).exists():
            print(f"  ⚠ Attenzione: «{cartella}» non risulta raggiungibile ora.")
            print("    Se è un'unità di rete, assicurati che sia collegata prima di avviare.")

    print("\nProtezione della cartella: se rispondi sì, il programma potrà solo LEGGERE i")
    print("documenti e non potrà mai scriverci dentro (consigliato).")
    sola_lettura = _si_no("Impostare la sola lettura?", True)

    print("\nCome vuoi usarlo?")
    print("  1) Solo ricerca — tutto resta su questo PC, non serve nessuna chiave. Cerchi")
    print("     parole e frasi nei documenti e ottieni i passaggi con il riferimento.")
    print("  2) Con l'assistente — puoi fare domande in linguaggio naturale e farti")
    print("     preparare gli aggiornamenti dei registri. Per capire la domanda e scrivere")
    print("     la risposta vengono inviati a un servizio esterno (Anthropic) la tua domanda")
    print("     e i soli passaggi trovati. Serve una chiave API.")
    assistito = _chiedi("Scelta [1/2] ", "1") == "2"

    chiave = ""
    if assistito:
        print("\nLa chiave si crea su https://console.anthropic.com/settings/keys")
        chiave = _chiedi("Incolla la chiave (inizia con sk-ant-...), oppure Invio per aggiungerla dopo\n> ")
        if not chiave:
            print("  Nessuna chiave: parto in modalità «solo ricerca». Potrai cambiarla")
            print("  in seguito rieseguendo questa procedura.")
            assistito = False

    contenuto = f"""# Configurazione di SGS Live — creata dalla procedura guidata.
# Per rifarla: python sgs.py configura

# Cartelle dei documenti del SGS (separate da «;»), lette e mai modificate.
SGS_DOCUMENTI={cartelle}

# 1 = il programma non scrive mai nelle cartelle qui sopra.
SGS_SOLA_LETTURA={"1" if sola_lettura else "0"}

# File e cartelle da non indicizzare mai (utile per i documenti con dati personali).
SGS_ESCLUDI=~$*;*.tmp;*.bak;.*;Archivio storico*;Riservato*;Dati personali*;*Bozza*

# locale = nessun dato esce da questo PC · assistito = risposte in linguaggio naturale
SGS_MODALITA={"assistito" if assistito else "locale"}
{"ANTHROPIC_API_KEY=" + chiave if chiave else "#ANTHROPIC_API_KEY=sk-ant-..."}
SGS_MODELLO=claude-opus-5

# Archivio locale (indice, registri, tracciabilità).
SGS_DB=./sgs_live.db
# 127.0.0.1 = raggiungibile solo da questo PC.
SGS_INDIRIZZO=127.0.0.1
SGS_PORTA=8770
"""
    percorso_env.write_text(contenuto, encoding="utf-8")

    print("\n" + "-" * 68)
    print(f"Configurazione salvata in: {percorso_env}")
    print(f"  cartelle   : {cartelle}")
    print(f"  sola lettura: {'sì' if sola_lettura else 'no'}")
    print(f"  modalità   : {'con assistente' if assistito else 'solo ricerca (nessun dato esce)'}")
    print("-" * 68)
    return percorso_env
