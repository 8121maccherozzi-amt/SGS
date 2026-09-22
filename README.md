# SGS Live

Dashboard del Sistema di Gestione della Sicurezza di AMT S.p.A. per i sistemi di trasporto a guida
vincolata (MET, FGC, FPG, FIL). Permette di **interrogare in linguaggio naturale** i documenti del
SGS e di **proporre aggiornamenti** al registro normative e agli indicatori IPS, con conferma
esplicita dell'operatore e tracciabilità completa.

## Cosa fa

| Funzione | Descrizione |
|---|---|
| Indicizzazione | Manuale, Procedure, Istruzioni Operative e Registri in PDF, DOCX, XLSX/XLSM, TXT, MD, letti da una o più cartelle indicate dall'utente |
| Ricerca documentale | Risponde citando codice documento, revisione, pagina e sezione (per i registri Excel, il foglio) |
| Estratti letterali | Sotto ogni risposta compaiono i passaggi effettivi dei documenti, con le parole della domanda evidenziate, la cartella di provenienza e il collegamento al file originale |
| Registro normative | TGV_MSGS_RGS_01: riferimenti, applicabilità per sistema, stato, impatto, azioni, scadenze |
| Indicatori IPS | TGV_PRC_06_RGS_02: anagrafica, soglie di Allarme/Intervento, misure per periodo, stato automatico rispetto alle soglie (TGV_PRC_11) |
| Proposte di modifica | L'assistente non scrive: prepara proposte con anteprima delle differenze, che l'operatore conferma o rifiuta |
| Tracciabilità | Ogni scrittura registrata con operatore, data/ora, valore precedente e successivo, origine |
| Esportazioni | CSV di norme, indicatori, misure, proposte e log di audit |

## Provarlo (anche senza sapere programmare)

Il programma gira sul tuo computer. Servono circa dieci minuti la prima volta.

**1. Verifica se Python c'è già** (è il motore su cui gira il programma; spesso sui PC aziendali
è già installato)
Doppio clic su **`verifica.bat`** (Windows) o `./verifica.sh` (macOS/Linux): non installa e non
modifica nulla, dice soltanto se il computer è pronto.
In alternativa, a mano: tasto Windows → scrivi `cmd` → Invio → scrivi `py --version` → Invio.
Se compare `Python 3.10` o superiore, ci siamo.

Se manca: <https://www.python.org/downloads/windows/> — nella prima schermata spunta
**«Add python.exe to PATH»**, e scegli l'installazione **«solo per me»**, che di norma non
richiede i diritti di amministratore. Se i criteri aziendali la bloccano, serve una richiesta
all'assistenza informatica.

**2. Scarica il programma**
Su GitHub, nella pagina del progetto: pulsante verde **Code → Download ZIP**. Estrai la cartella
dove preferisci, per esempio sul Desktop.

**3. Avvialo**
- Windows: doppio clic su **`avvia.bat`**
- macOS / Linux: doppio clic su **`avvia.sh`** (o `./avvia.sh` dal Terminale)

La prima volta prepara tutto da solo e poi ti fa tre domande:
- **dove sono i documenti del SGS** — incolla il percorso della cartella (va bene anche un'unità di
  rete, es. `S:\SGS\Documentazione`); puoi indicarne più di una separandole con `;`
- **sola lettura?** — rispondi sì: il programma potrà solo leggere e non scriverà mai in quella cartella
- **come vuoi usarlo** — scegli **1** per provarlo subito: cerca nei documenti, tutto resta sul tuo PC
  e non serve nessuna chiave. La **2** aggiunge l'assistente che risponde a domande scritte
  normalmente, e richiede una chiave a pagamento

Poi il browser si apre da solo su `http://127.0.0.1:8770`.

**4. Prima indicizzazione**
Vai nella scheda **Documenti**: lì c'è il riquadro con le cartelle da leggere (si cambiano in
qualsiasi momento, una per riga) e il pulsante **«Salva e indicizza»**. Premilo e aspetta: il
programma dice quanti file ha trovato in ciascuna cartella e quanti ne ha letti. Finché non lo
fai, il contatore «Documenti indicizzati» resta a zero. Ripeti ogni volta che i documenti cambiano.

Per chiudere: `Ctrl+C` nella finestra nera, oppure chiudila.
Per rifare le domande iniziali: `python sgs.py configura`.

Se preferisci partire con dati finti per capire come funziona, prima dell'avvio esegui
`python sgs.py esempi`: carica 5 norme, 6 indicatori e un documento di prova.

## Avvio rapido (per chi usa il terminale)

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python sgs.py configura   # scrive .env rispondendo a tre domande
./.venv/bin/python sgs.py esempi      # dati dimostrativi (facoltativo)
./.venv/bin/python sgs.py avvia       # http://127.0.0.1:8770
```

In alternativa si può copiare `.env.example` in `.env` e compilarlo a mano. La chiave API,
necessaria solo in modalità `assistito`, si ottiene su
<https://console.anthropic.com/settings/keys>.

### Comandi

| Comando | Effetto |
|---|---|
| `verifica.bat` / `./verifica.sh` | Controlla se il computer ha i requisiti, senza installare nulla |
| `python3 sgs.py avvia` | Avvia la dashboard e apre il browser (`--niente-browser` per evitarlo) |
| `python3 sgs.py configura` | Rifà la configurazione guidata (cartelle, sola lettura, modalità) |
| `python3 sgs.py indicizza [--forza] [--cartella X]` | (Re)indicizza le cartelle sorgente |
| `python3 sgs.py esempi` | Carica dati dimostrativi (5 norme, 6 IPS, 1 documento fittizio) |
| `python3 sgs.py importa file.csv --tipo norme\|indicatori` | Importa un registro esistente esportato in CSV |

## Dove stanno i dati di input

Si indicano in `.env` una o più **cartelle sorgente**, separate da `;`. Vengono lette e mai
modificate: possono essere cartelle locali, unità di rete mappate o percorsi UNC.

```ini
# Windows
SGS_DOCUMENTI=\\srv-file\SGS\Documentazione;S:\SGS\Registri
# Linux / macOS
SGS_DOCUMENTI=/mnt/sgs/documentazione;/mnt/sgs/registri
SGS_SOLA_LETTURA=1
```

| Variabile | Effetto |
|---|---|
| `SGS_DOCUMENTI` | Cartelle da indicizzare, separate da `;`, ricorsive. È il valore iniziale: si cambia poi dalla scheda Documenti, e la scelta viene salvata in `impostazioni.json`, che ha la precedenza |
| `SGS_SOLA_LETTURA=1` | Disattiva il caricamento di file dalla dashboard: nulla viene mai scritto nelle cartelle sorgente |
| `SGS_ESCLUDI` | Glob di file e cartelle da non indicizzare mai — serve a tenere fuori dall'indice i documenti con dati personali o sanitari (default: `~$*;*.tmp;*.bak;.*;Archivio storico*;Riservato*;Dati personali*;*Bozza*`) |
| `SGS_MODALITA` | `assistito` (ricerca locale + risposte del modello) oppure `locale` (nessuna chiamata esterna) |
| `SGS_CARTELLA_CARICAMENTI` | Dove atterrano i file caricati dalla dashboard, quando il caricamento è abilitato |
| `SGS_DB` | File SQLite con indice, registri e log di tracciabilità |
| `SGS_INDIRIZZO` | `127.0.0.1` di default: raggiungibile solo dal PC su cui gira |

### Temi (cartelle) e tipologie (sigle)

L'archivio è organizzato per **aree tematiche di processo**, non per tipologia di documento. I due
dati vengono letti da fonti diverse:

| Dato | Da dove viene | Esempio |
|---|---|---|
| **Tema** | Nome della cartella di primo livello, ignorando la numerazione | `3 - Formazione` → Formazione |
| **Tipologia** | Sigla nel nome del file | `TGV_IST_04` → Istruzione operativa |
| **Sistema** | Prefisso nel nome del file; in mancanza, una cartella che nomini il sistema | `MET_PRC_06` → MET |

Aree tematiche riconosciute (`TEMI` in `sgs_live/ingest.py`, con i sinonimi che le richiamano):
Manuale SGS · Procedure Organizzative · Formazione · Valutazione dei rischi · Regolamento di
Esercizio · Manutenzione Infrastruttura · Manutenzione Veicoli - SRM · Monitoraggio · Non
Conformità ed Eventi Indesiderati. Una cartella non riconosciuta diventa comunque un tema, con il
proprio nome.

Tipologie previste dalla procedura di gestione della documentazione (`TIPI_DOCUMENTO` in
`sgs_live/config.py`): POL, MSGS, MSRM, DVR, PAS, RAS, RIS (strategici); PRC, IST, RDE, ODS, RGS,
MOD (organizzativi e operativi).

Conseguenze pratiche:

- il tema è indicizzato insieme al testo, quindi una domanda che richiama un'area («le competenze
  di chi manutiene i rotabili») fa emergere i documenti di quell'area anche se non ne usa le
  parole esatte;
- l'assistente può restringere la ricerca a un tema, e la mappa delle aree presenti gli viene
  fornita a ogni domanda;
- ogni estratto mostra il tema di provenienza.

Codice, tipo, sistema e revisione sono dedotti dal nome file secondo la naming convention del SGS —
`TGV_PRC_11 - Monitoraggio prestazioni rev 02.pdf`, `MET_PRC_06_RGS_01 - Hazard Log rev 03.xlsx`.
Se due file diversi producono lo stesso codice, il secondo riceve un suffisso (`TGV_PRC_11#2`).
Le cartelle si cambiano dalla dashboard (scheda Documenti) oppure in `.env`. Cambiandole, i
documenti che non appartengono più alle cartelle scelte escono dall'indice, con registrazione in
audit. Premere **Salva e indicizza** dopo ogni revisione: l'indice segue l'impronta dei file,
rileva le modifiche e toglie dall'indice i documenti non più presenti.

I registri Excel (Hazard Log, registro IPS, registro NC, prescrizioni ANSFISA) sono indicizzati un
foglio alla volta, e la citazione riporta il nome del foglio.

## Che cosa resta in locale e che cosa no

| Elaborazione | Dove avviene |
|---|---|
| Lettura dei file, estrazione del testo, indice full-text | Sulla macchina, nel file SQLite |
| Ricerca, registri normative e IPS, proposte, log di tracciabilità | Sulla macchina |
| Formulazione della risposta in linguaggio naturale (`SGS_MODALITA=assistito`) | **API Anthropic**: vengono inviati la domanda e i soli passaggi recuperati, non l'archivio |
| Tutto, senza alcuna trasmissione (`SGS_MODALITA=locale`) | Sulla macchina: la scheda diventa «Ricerca documentale», l'assistente è disattivato e l'endpoint `/api/chat` risponde 409 |

Non esiste una terza via con questa architettura: la comprensione della domanda in linguaggio
naturale richiede un modello, e il modello è remoto. Se la risposta conversazionale serve ma il
dato non può uscire, l'alternativa è un modello eseguito in azienda (Ollama o simili, su GPU
dedicata) — `sgs_live/agent.py` è l'unico file da adattare, a prezzo di una qualità inferiore nella
comprensione della domanda e nella redazione della risposta.

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

Un solo file SQLite (`sgs_live.db`) e i documenti nelle cartelle indicate, lette senza mai essere
modificate. L'unica comunicazione verso l'esterno è la chiamata all'API Anthropic, assente in
modalità `locale`.

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
| **Trasferimento dati al fornitore API** | In modalità `assistito` i passaggi recuperati vengono inviati all'API Anthropic | Valutazione con il DPO; `SGS_ESCLUDI` per tenere fuori dall'indice i documenti con dati personali, sanitari o disciplinari; `SGS_MODALITA=locale` se la trasmissione non è ammissibile |
| **Accesso alle cartelle sorgente** | L'applicazione legge tutto ciò che trova sotto i percorsi indicati | Puntare a una cartella di sola lettura, con un'utenza di servizio abilitata in lettura, e verificare le esclusioni prima della prima indicizzazione |
| **Nessuna autenticazione** | Il server non ha login: chiunque raggiunga la porta opera come l'operatore che digita il proprio nome | Tenere `SGS_INDIRIZZO=127.0.0.1` (solo macchina locale); per l'uso condiviso serve un reverse proxy con autenticazione aziendale |
| **Integrità del log** | Il log è append-only per costruzione, ma il file SQLite resta modificabile da chi ha accesso al filesystem | Backup periodico e conservazione su supporto controllato, se l'evidenza deve valere verso ANSFISA |
| **PDF scansionati** | Senza testo estraibile non entrano nell'indice (l'indicizzazione lo segnala) | OCR preventivo dei documenti storici |
| **Ricerca lessicale** | BM25 trova le parole, non i concetti: una domanda formulata con termini diversi dal documento può non recuperare il passaggio | Il dizionario di sinonimi è in `sgs_live/retrieval.py` e va esteso con la terminologia aziendale; in prospettiva, ricerca semantica |
| **Valore documentale** | La risposta dell'assistente non è un documento del SGS | Restano autorevoli i documenti approvati: SGS Live è uno strumento di consultazione e di supporto alla compilazione |

## Requisiti

Python 3.11+, una chiave API Anthropic. Nessun servizio esterno oltre all'API del modello.
