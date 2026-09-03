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

Formato atteso (JSON, generato da `notebooklm login` con i cookie del
browser sulla pagina di Gemini Notebook, oppure copiato manualmente):

```json
{
  "cookies": [
    { "name": "SID", "value": "...", "domain": ".google.com" },
    { "name": "__Secure-1PSIDTS", "value": "..." }
  ],
  "origins": [],
  "notebooklm": { "version": 1, "account": { "authuser": 0, "email": "tu@example.com" } }
}
```

I cookie **`SID`** e **`__Secure-1PSIDTS`** sono obbligatori; almeno uno tra
`OSID` oppure la coppia `APISID`+`SAPISID`+`LSID` è fortemente consigliato.

Per generare questo JSON dal tuo browser, il modo più semplice è:

```bash
pip install "notebooklm-py[browser]"
notebooklm login --browser-cookies chrome   # legge i cookie dal profilo Chrome locale
cat ~/.notebooklm/profiles/default/storage_state.json   # contenuto da usare come NOTEBOOKLM_AUTH_JSON
```

## Uso

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
