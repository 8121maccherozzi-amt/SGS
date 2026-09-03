# Connettore NotebookLM (non ufficiale)

Script che elenca i notebook del tuo account NotebookLM (Gemini Notebook) e
ne esporta localmente fonti e note. Si appoggia alla libreria open source
[`notebooklm-py`](https://github.com/teng-lin/notebooklm-py), che dialoga
con l'API interna (non documentata) di NotebookLM tramite i cookie di
sessione del browser.

## ⚠️ Avvertenze

- **Non è un'integrazione ufficiale Google.** Usa endpoint interni non
  documentati, che possono cambiare o smettere di funzionare senza preavviso.
- **Il payload di autenticazione equivale alle tue credenziali Google.**
  Non va mai committato nel repository, incollato in log, issue, PR o
  altrove. Trattalo come una password.
- Verifica la compatibilità con i termini di servizio di Google prima di un
  uso continuativo o automatizzato (es. su CI).

## Installazione

```bash
pip install -r tools/notebooklm/requirements.txt
```

## Autenticazione

Lo script legge la variabile d'ambiente **`NOTEBOOKLM_AUTH_JSON`** (questo
è il nome esatto atteso dalla libreria `notebooklm-py` per l'autenticazione
inline via cookie, pensata per script/CI). Se hai già predisposto una
variabile con un nome diverso, rinominala in `NOTEBOOKLM_AUTH_JSON` oppure
esportala prima di lanciare lo script:

```bash
export NOTEBOOKLM_AUTH_JSON="$(cat storage_state.json)"
```

### Formati accettati

`cookie_to_auth.py` riconosce automaticamente tre formati di input e li
normalizza nello `storage_state` atteso dalla libreria:

| Formato | Esempio |
|---|---|
| Riga di header HTTP `Cookie:` | `cookie: SID=...; HSID=...; SAPISID=...` |
| Array JSON da estensione browser | `[{"name": "SID", "value": "...", "domain": ".google.com"}, ...]` |
| `storage_state` già pronto | `{"cookies": [...], "origins": []}` |

Il dominio `notebook.google.com` viene ricondotto a `notebooklm.google.com`,
e i valori `sameSite` non standard (es. `no_restriction`) sono normalizzati.

### Cookie obbligatori

I cookie **`SID`** e **`__Secure-1PSIDTS`** sono obbligatori; almeno uno tra
`OSID` oppure la coppia `APISID`+`SAPISID`+`LSID` è fortemente consigliato.

⚠️ **Attenzione agli export parziali.** `SID`, `HSID`, `APISID` e `LSID` non
hanno il flag `Secure`: le estensioni con filtro "solo cookie secure" e le
letture parziali del profilo Chrome 127+ (App-Bound Encryption) li perdono
silenziosamente, producendo un payload che sembra completo ma viene
rifiutato con `Missing required cookies: SID`. Lo script diagnostica
esplicitamente questo caso. La riga `cookie:` presa dagli header di
richiesta li contiene sempre tutti.

Per generare il JSON dal tuo browser con la libreria:

```bash
pip install "notebooklm-py[browser]"
notebooklm login --browser-cookies chrome   # legge i cookie dal profilo Chrome locale
cat ~/.notebooklm/profiles/default/storage_state.json   # contenuto da usare come NOTEBOOKLM_AUTH_JSON
```

## Uso

### Flusso completo in un comando

```bash
bash tools/notebooklm/run_export.sh
# oppure: bash tools/notebooklm/run_export.sh percorso/cookie.txt cartella_output
```

Lo script prende i cookie, in ordine, da:

1. il file passato come primo argomento (default `cookie.txt` nella radice del repo);
2. la variabile d'ambiente `NOTEBOOKLM_AUTH_JSON`, se quel file non esiste.

Il secondo caso è quello utile su CI o su Claude Code remoto, dove non si
possono depositare file locali: basta impostare la variabile nella
configurazione dell'ambiente. Poi lo script normalizza i cookie, verifica
l'autenticazione ed esegue l'export. `cookie.txt` e la cartella di export
sono esclusi da git.

**Come ottenere la riga `cookie:`**: su `notebooklm.google.com` (loggato con
l'account giusto) premi F12 → scheda **Network** → F5 per ricaricare → clic
sulla prima richiesta a `notebooklm.google.com` → **Headers** → **Request
Headers** → tasto destro sul valore di `cookie:` → *Copy value*. Il cookie
`__Secure-1PSIDTS` ruota spesso: usa una copia fresca.

### Solo l'export (autenticazione già configurata)

```bash
# Elenca tutti i notebook e ne esporta fonti/note in ./notebooklm_export
python3 tools/notebooklm/connector.py

# Esporta un solo notebook, in una cartella a scelta
python3 tools/notebooklm/connector.py --notebook <ID_NOTEBOOK> --output ./export_singolo
```

Output per ogni notebook:
- una cartella con un file `.txt` per fonte (testo integrale indicizzato)
  e un file `.md` per nota;
- `_metadata.json` con titoli e ID;
- `index.json` nella cartella radice con l'elenco di tutti i notebook esportati.

## Sicurezza

- La cartella di export (default `notebooklm_export/`) e qualunque file
  contenente cookie/token sono esclusi da git tramite il `.gitignore` del
  repository: **non forzare mai `git add` su questi file**.
- Se sospetti che il cookie sia stato esposto, invalida la sessione
  (logout su tutti i dispositivi Google) e rigenera il payload.
