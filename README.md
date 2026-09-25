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

### SGS Learning: grafica, audio e marchio

- **Qualità grafica**: in Impostazioni il valore predefinito è *Automatica*. Con schede video integrate (Intel UHD/Iris, AMD Radeon Graphics) parte da *Media*; se durante il gioco la fluidità resta sotto i 24 fps scende da sola a *Bassa*.
- **Audio**: il sottofondo di stazione suona solo all'arrivo e alla partenza dei treni.
- **Genova e AMT**: manifesti illustrati disegnati dal gioco (Lanterna, Porto Antico, Boccadasse, De Ferrari, Zecca–Righi, Principe–Granarolo), mappa della linea M, biglietteria, annunci «AMT informa». Non contengono immagini o loghi scaricati da internet.
- **Logo aziendale**: Impostazioni › *Logo aziendale* › *Carica…* (PNG, JPG o SVG). Il logo sostituisce la scritta «AMT» su titolo, treni, tesserini, manifesti e mappe; resta solo nel browser di chi lo carica. Usare il file fornito dalla Comunicazione aziendale.
