"""Configurazione della pipeline delle mappe."""

# Regione scaricata (lat/lon) — copre entrambe le aree disegnate
REGION = dict(lat_min=25.0, lat_max=72.0, lon_min=-35.0, lon_max=50.0)

# Scadenze (ore) delle mappe
STEPS_LONG = list(range(0, 121, 6)) + list(range(132, 169, 12))   # fino a +168h
STEPS_ICON = list(range(0, 121, 6))                               # ICON-EU arriva a +120h

MODELS = {
    "gfs":   {"label": "GFS",   "org": "NOAA",  "res": "0.25°",  "steps": STEPS_LONG},
    "ecmwf": {"label": "ECMWF", "org": "ECMWF", "res": "0.25°",  "steps": STEPS_LONG},
    "icon":  {"label": "ICON",  "org": "DWD",   "res": "0.0625°", "steps": STEPS_ICON},
}

# Aree disegnate: estensione [lon_min, lon_max, lat_min, lat_max] e centro della proiezione
AREAS = {
    "it": {"label": "Italia", "extent": [5.0, 20.5, 35.5, 47.8], "center": (12.5, 42.0)},
    "eu": {"label": "Europa", "extent": [-22.0, 40.0, 33.0, 68.0], "center": (9.0, 50.0)},
}

# Mappe disponibili e campi necessari
MAPS = {
    "z500":  {"label": "Geopotenziale 500 hPa + T 850 hPa", "short": "500 hPa", "needs": ["z500", "t850"]},
    "pcp":   {"label": "Pressione al suolo + pioggia 6 h",  "short": "Pioggia",  "needs": ["mslp", "tp6"]},
    "t2m":   {"label": "Temperatura a 2 m",                  "short": "Temp. 2 m", "needs": ["t2m"]},
    "vento": {"label": "Vento a 10 m",                       "short": "Vento",   "needs": ["u10", "v10"]},
    "cape":  {"label": "CAPE (energia per temporali)",       "short": "CAPE",    "needs": ["cape"]},
}

CREDITS = {
    "gfs": "Dati: NOAA/NCEP GFS",
    "ecmwf": "Dati: ECMWF Open Data (CC BY 4.0)",
    "icon": "Dati: Deutscher Wetterdienst (ICON-EU)",
}
