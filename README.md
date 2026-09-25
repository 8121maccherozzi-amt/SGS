# SGS
Progetti relativi al SGS

## Giochi formativi (`giochi/`)

| File | Contenuto |
|---|---|
| `metro-arena-genova.html` | Arcade 2D |
| `ultima-corsa-3d.html` | Survival 3D con parte SGS |
| `turno-di-esercizio.html` | Audit SGS in stazione |
| `sgs-learning.html` | Percorso formativo: motore fisso, contenuti da pacchetto |

### SGS Learning: pacchetti contenuti (`giochi/pacchetti/`)

- `sgs-learning-modulo1.xlsx`: Modulo 1 (normativa di riferimento) da revisionare. È il contenuto predefinito del gioco.
- `sgs-learning-modello.xlsx`: modello da compilare, con una tappa d'esempio già caricabile.
- `sgs-learning-modulo1.json`: stesso Modulo 1 in formato pacchetto, incorporato nel gioco.
- `pack_to_xlsx.py`: rigenera il foglio Excel da un pacchetto JSON (`python3 pack_to_xlsx.py pacchetto.json uscita.xlsx`).

Nel gioco: schermata iniziale › **Carica modulo** › file `.xlsx` o `.json`. Il gioco controlla il file e, se trova errori, li elenca con foglio e riga senza caricarlo. Il modulo caricato resta attivo nel browser finché non si torna al Modulo 1 predefinito.
