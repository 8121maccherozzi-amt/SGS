#!/usr/bin/env python3
"""SGS Live — riga di comando.

  python3 sgs.py avvia        avvia la dashboard su http://127.0.0.1:8770
  python3 sgs.py indicizza    (re)indicizza la cartella dei documenti
  python3 sgs.py esempi       carica dati di esempio (norme, indicatori, un documento fittizio)
  python3 sgs.py importa registro.csv --tipo norme|indicatori
"""
from __future__ import annotations

import argparse
import csv
import os
import socket
import shutil
import sys
import threading
import webbrowser
from pathlib import Path

from sgs_live.config import (CARTELLA_DOCUMENTI, CARTELLE_DOCUMENTI, INDIRIZZO, MODALITA,
                             PORTA, RADICE, SOLA_LETTURA)
from sgs_live.db import adesso, connessione, inizializza, registra_audit
from sgs_live.ingest import indicizza_cartella
from sgs_live.tools import CAMPI_INDICATORE, CAMPI_NORMA

NUMERICI = {"soglia_allarme", "soglia_intervento"}


def _importa(percorso: Path, tipo: str, utente: str) -> int:
    campi_ammessi = CAMPI_NORMA if tipo == "norme" else CAMPI_INDICATORE
    with percorso.open(encoding="utf-8-sig", newline="") as f:
        campione = f.read(4096)
        f.seek(0)
        delimitatore = ";" if campione.count(";") >= campione.count(",") else ","
        righe_csv = list(csv.DictReader(f, delimiter=delimitatore))

    conteggio = 0
    with connessione() as con:
        for r in righe_csv:
            campi = {k.strip(): (v.strip() if isinstance(v, str) else v)
                     for k, v in r.items() if k and k.strip() in campi_ammessi and (v or "").strip()}
            for k in NUMERICI & set(campi):
                campi[k] = float(str(campi[k]).replace(",", "."))
            if tipo == "norme":
                if not campi.get("riferimento"):
                    continue
                esistente = con.execute("SELECT id FROM norme WHERE lower(riferimento)=lower(?)",
                                        (campi["riferimento"],)).fetchone()
                tabella, chiave = "norme", campi["riferimento"]
            else:
                if not campi.get("codice") or not campi.get("sistema"):
                    continue
                esistente = con.execute(
                    "SELECT id FROM indicatori WHERE lower(codice)=lower(?) AND sistema=?",
                    (campi["codice"], campi["sistema"])).fetchone()
                tabella, chiave = "indicatori", f"{campi['codice']}/{campi['sistema']}"

            if esistente:
                con.execute(f"UPDATE {tabella} SET {', '.join(f'{k}=?' for k in campi)}, aggiornato_il=? WHERE id=?",
                            (*campi.values(), adesso(), esistente["id"]))
                record_id = esistente["id"]
            else:
                colonne = list(campi) + ["creato_il", "aggiornato_il"]
                con.execute(f"INSERT INTO {tabella} ({','.join(colonne)}) VALUES ({','.join('?' * len(colonne))})",
                            (*campi.values(), adesso(), adesso()))
                record_id = con.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
            registra_audit(con, utente=utente, azione=f"{tabella}_importato", entita=tabella,
                           entita_id=record_id, dopo=campi, origine="importazione_csv",
                           note=f"da {percorso.name}: {chiave}")
            conteggio += 1
    return conteggio


def main() -> int:
    parser = argparse.ArgumentParser(description="SGS Live")
    sotto = parser.add_subparsers(dest="comando", required=True)
    p_avvia = sotto.add_parser("avvia")
    p_avvia.add_argument("--niente-browser", action="store_true",
                         help="non aprire automaticamente il browser")
    sotto.add_parser("configura")
    p_ind = sotto.add_parser("indicizza")
    p_ind.add_argument("--forza", action="store_true",
                       help="reindicizza anche i file non modificati")
    p_ind.add_argument("--cartella", action="append",
                       help="indicizza solo questa cartella (ripetibile)")
    sotto.add_parser("esempi")
    p_imp = sotto.add_parser("importa")
    p_imp.add_argument("file")
    p_imp.add_argument("--tipo", choices=["norme", "indicatori"], required=True)
    p_imp.add_argument("--utente", default="importazione")
    argomenti = parser.parse_args()

    inizializza()

    if argomenti.comando == "configura":
        from sgs_live.configura import esegui
        esegui(forza=True)
        print("\nOra puoi avviare il programma.")
        return 0

    if argomenti.comando == "avvia":
        if not (RADICE / ".env").exists():
            from sgs_live.configura import esegui
            esegui()
            # La configurazione si legge all'avvio: riparto per applicarla.
            os.execv(sys.executable, [sys.executable, *sys.argv])

        with socket.socket() as sonda:
            if sonda.connect_ex((INDIRIZZO, PORTA)) == 0:
                print(f"\nLa porta {PORTA} è già occupata: probabilmente SGS Live è già aperto.")
                print(f"Prova ad andare su http://{INDIRIZZO}:{PORTA} nel browser.")
                print("Se invece è un altro programma, cambia SGS_PORTA nel file .env.\n")
                return 1

        import uvicorn
        indirizzo = f"http://{INDIRIZZO}:{PORTA}"
        print(f"SGS Live → {indirizzo}")
        print(f"  modalità: {MODALITA}" + ("  (sola lettura)" if SOLA_LETTURA else ""))
        for cartella in CARTELLE_DOCUMENTI:
            print(f"  cartella: {cartella}" + ("" if cartella.exists() else "  ⚠ non raggiungibile"))
        print("\nPer chiudere il programma: Ctrl+C in questa finestra.\n")
        if not argomenti.niente_browser:
            threading.Timer(1.5, webbrowser.open, [indirizzo]).start()
        uvicorn.run("sgs_live.main:app", host=INDIRIZZO, port=PORTA, reload=False)
        return 0

    if argomenti.comando == "indicizza":
        cartelle = [Path(c) for c in (argomenti.cartella or [])] or None
        for esito in indicizza_cartella(cartelle, forza=argomenti.forza):
            passaggi = esito.get("chunk")
            print(f"  {esito['stato']:14s} {esito['codice']}" +
                  (f" ({passaggi} passaggi)" if passaggi else ""))
        return 0

    if argomenti.comando == "esempi":
        origine = RADICE / "dati_esempio"
        CARTELLA_DOCUMENTI.mkdir(parents=True, exist_ok=True)
        for documento in origine.glob("*.md"):
            shutil.copy2(documento, CARTELLA_DOCUMENTI / documento.name)
        print(f"norme importate:      {_importa(origine / 'norme.csv', 'norme', 'esempi')}")
        print(f"indicatori importati: {_importa(origine / 'indicatori.csv', 'indicatori', 'esempi')}")
        for esito in indicizza_cartella(utente="esempi"):
            print(f"  {esito['stato']:14s} {esito['codice']}")
        return 0

    if argomenti.comando == "importa":
        n = _importa(Path(argomenti.file), argomenti.tipo, argomenti.utente)
        print(f"{n} righe importate in «{argomenti.tipo}».")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
