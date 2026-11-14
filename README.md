# Modelli Meteo

App Android con le mappe dei modelli **GFS**, **ECMWF** e **ICON**, disegnate con una grafica propria, e i meteogrammi per località con il confronto tra 6 modelli.

## Come funziona

```
GitHub Actions (4 volte al giorno)
  └─ pipeline/render.py
       ├─ scarica GFS (NOAA), ECMWF (Open Data), ICON-EU (DWD)
       ├─ disegna le mappe (Italia + Europa)
       └─ pubblica tutto su GitHub Pages  →  l'app scarica le mappe da lì

App Android (android/)
  ├─ Mappe: scelta modello, mappa, area, slider, animazione, confronto, zoom
  ├─ Località: ricerca città, posizione GPS, preferiti, grafici multi-modello (Open-Meteo)
  └─ Info: corse disponibili e fonti
```

**Mappe:** geopotenziale 500 hPa + T 850 hPa, termiche 850 hPa, pressione + pioggia 6 h, temperatura 2 m, vento 10 m, CAPE (GFS e ICON).
**Aree:** Italia, Europa, Nord America, Emisfero Nord.
**Scadenze:** ogni 6 ore fino a +120h, poi ogni 12 ore: GFS fino a +384h, ECMWF fino a +360h, ICON (globale) fino a +180h.

## Installazione (una volta sola)

1. Su GitHub crea un repository **pubblico** chiamato `modelli-meteo` (account `biagiopaparella5-hash`).
2. Carica tutto il contenuto di questa cartella, inclusa la cartella nascosta `.github`. Su GitHub: *Add file → Upload files*, poi trascina i file.
3. Vai in **Settings → Pages** e alla voce *Source* scegli **GitHub Actions**.
4. Vai in **Actions → Mappe meteo → Run workflow** per generare subito le prime mappe. La prima volta ci vogliono circa 20-30 minuti.
5. Vai in **Actions → Compila APK**: il workflow parte da solo al caricamento dei file. Alla fine scarica l'artefatto **ModelliMeteo-apk** e installa `ModelliMeteo.apk` sul telefono.

Da quel momento le mappe si aggiornano da sole, verso le 05:20, 11:20, 17:20 e 23:20 (ora italiana).
L'app funziona anche da browser: `https://biagiopaparella5-hash.github.io/modelli-meteo/app/`

## Note

- Se rinomini il repository, modifica `android/app/src/main/assets/www/config.js` (riga `DATA_URL`).
- L'APK è firmato con una chiave fissa (`android/app/debug.keystore`), quindi le nuove versioni si installano sopra la vecchia senza doverla disinstallare.
- GitHub sospende i workflow programmati se il repository resta senza modifiche per 60 giorni: in quel caso basta riattivarli dalla scheda Actions.
- Per provare la grafica senza scaricare dati: `cd pipeline && python render.py --test --out ../site`

## Fonti dei dati

- GFS: NOAA/NCEP
- ECMWF: ECMWF Open Data, licenza CC BY 4.0
- ICON-EU: Deutscher Wetterdienst
- Previsioni per località: Open-Meteo.com
