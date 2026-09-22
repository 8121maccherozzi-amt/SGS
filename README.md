# SGS Live

Dashboard del Sistema di Gestione della Sicurezza di AMT S.p.A. per i sistemi di trasporto a guida
vincolata (MET, FGC, FPG, FIL). Permette di **interrogare in linguaggio naturale** i documenti del
SGS e di **proporre aggiornamenti** al registro normative e agli indicatori IPS, con conferma
esplicita dell'operatore e tracciabilità completa.

## Cosa fa

| Funzione | Descrizione |
|---|---|
| Ricerca documentale | Indicizza Manuale, Procedure, Istruzioni Operative e Registri (PDF, DOCX, TXT, MD) e risponde citando codice documento, revisione, pagina e sezione |
| Estratti letterali | Restituisce il testo originale del passaggio, non una parafrasi |
| Registro normative | TGV_MSGS_RGS_01: riferimenti, applicabilità per sistema, stato, impatto, azioni, scadenze |
| Indicatori IPS | TGV_PRC_06_RGS_02: anagrafica, soglie di Allarme/Intervento, misure per periodo, stato automatico rispetto alle soglie (TGV_PRC_11) |
| Proposte di modifica | L'assistente non scrive: prepara proposte con anteprima delle differenze, che l'operatore conferma o rifiuta |
| Tracciabilità | Ogni scrittura registrata con operatore, data/ora, valore precedente e successivo, origine |
| Esportazioni | CSV di norme, indicatori, misure, proposte e log di audit |

## Avvio rapido

```bash
./avvia.sh                       # crea .venv, installa le dipendenze, avvia il server
# poi: inserire ANTHROPIC_API_KEY in .env e rilanciare
```

In alternativa, senza lo script:

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env             # inserire ANTHROPIC_API_KEY
./.venv/bin/python sgs.py esempi # dati dimostrativi (facoltativo)
./.venv/bin/python sgs.py avvia  # http://127.0.0.1:8770
```

La chiave API si ottiene su <https://console.anthropic.com/settings/keys>.

### Comandi

| Comando | Effetto |
|---|---|
| `python3 sgs.py avvia` | Avvia la dashboard su `http://127.0.0.1:8770` |
| `python3 sgs.py indicizza [--forza]` | (Re)indicizza la cartella `documenti/` |
| `python3 sgs.py esempi` | Carica dati dimostrativi (5 norme, 6 IPS, 1 documento fittizio) |
| `python3 sgs.py importa file.csv --tipo norme\|indicatori` | Importa un registro esistente esportato in CSV |

### Caricamento dei documenti

Copiare i file in `documenti/` e premere **Reindicizza cartella** (oppure caricarli dalla scheda
Documenti). Il codice, il tipo, il sistema e la revisione vengono dedotti dal nome file secondo la
naming convention del SGS — es. `TGV_PRC_11 - Monitoraggio prestazioni rev 02.pdf`,
`MET_PRC_06_RGS_02 - Registro IPS.docx`. Reindicizzare dopo ogni revisione: l'indice segue
l'impronta del file e rileva le modifiche.

## Esempi di richiesta

- «Mostrami l'estratto del documento che parla di formazione della manutenzione veicoli»
- «Cosa prevede la TGV_PRC_11 al superamento della soglia di intervento?»
- «Quali IPS della metropolitana sono sopra la soglia di allarme?»
- «Registra IPS03 MET per il 2026-Q1 con valore 0,12, dato fornito da RTEM»
- «Aggiungi al registro norme la linea guida ANSFISA del 12/03/2026 su …, applicabile a MET e FPG, azione a carico del RSGS entro il 30/06»

Le ultime due producono una **proposta** visibile nella scheda «Modifiche da confermare»: nulla
viene scritto finché un operatore identificato non conferma.

## Architettura

```
sgs.py                  riga di comando
sgs_live/config.py      configurazione (.env)
sgs_live/db.py          schema SQLite, audit log, valutazione soglie
sgs_live/ingest.py      estrazione testo, chunking, metadati da nome file
sgs_live/retrieval.py   ricerca full-text FTS5 + BM25
sgs_live/tools.py       strumenti dell'assistente e applicazione delle proposte
sgs_live/agent.py       ciclo conversazionale con Claude
sgs_live/main.py        API HTTP (FastAPI)
web/                    dashboard (HTML/CSS/JS, nessuna dipendenza esterna)
```

Tutto gira in locale: un solo file SQLite (`sgs_live.db`) e i documenti nella cartella locale.
L'unica comunicazione verso l'esterno è la chiamata all'API Anthropic.

### Presidi di sicurezza applicativa

1. **Nessuna scrittura autonoma del modello.** Gli strumenti `proponi_*` creano righe in `proposte`;
   l'unico punto di scrittura sui registri è `applica_proposta`, invocato dalla conferma dell'operatore.
2. **Attribuzione obbligatoria.** Conferma e rifiuto richiedono il nome dell'operatore, altrimenti
   l'API risponde 400.
3. **Risposte ancorate alle fonti.** L'assistente è istruito a cercare prima di rispondere, a citare
   codice/revisione/pagina/sezione, a riportare gli estratti alla lettera e a dichiarare
   esplicitamente quando un'informazione non è nell'indice.
4. **Audit append-only.** Ogni proposta, conferma, rifiuto, modifica manuale e importazione è
   registrata con valore precedente e successivo.

## Punti aperti da decidere prima dell'uso operativo

| Tema | Perché conta | Opzione suggerita |
|---|---|---|
| **Doppia fonte del dato** | Se i registri ufficiali restano in Excel, SGS Live diventa una seconda copia: disallineamento e possibile rilievo in audit | Scegliere una fonte unica: o SGS Live con esportazione periodica firmata, o Excel con reimportazione via `sgs.py importa` dopo ogni aggiornamento |
| **Trasferimento dati al fornitore API** | I passaggi recuperati dai documenti vengono inviati all'API Anthropic | Valutazione con il DPO; escludere dall'indice documenti con dati personali (nominativi, abilitazioni, dati sanitari) |
| **Integrità del log** | Il log è append-only per costruzione, ma il file SQLite resta modificabile da chi ha accesso al filesystem | Backup periodico e conservazione su supporto controllato, se l'evidenza deve valere verso ANSFISA |
| **PDF scansionati** | Senza testo estraibile non entrano nell'indice (l'indicizzazione lo segnala) | OCR preventivo dei documenti storici |
| **Ricerca lessicale** | BM25 trova le parole, non i concetti: una domanda formulata con termini diversi dal documento può non recuperare il passaggio | Il dizionario di sinonimi è in `sgs_live/retrieval.py` e va esteso con la terminologia aziendale; in prospettiva, ricerca semantica |
| **Valore documentale** | La risposta dell'assistente non è un documento del SGS | Restano autorevoli i documenti approvati: SGS Live è uno strumento di consultazione e di supporto alla compilazione |

## Requisiti

Python 3.11+, una chiave API Anthropic. Nessun servizio esterno oltre all'API del modello.
