"""Configurazione della pipeline delle mappe."""

# Regione scaricata (lat/lon): tutto l'emisfero nord
REGION = dict(lat_min=14.0, lat_max=90.0, lon_min=-180.0, lon_max=180.0)


def _steps(last):
    """Ogni 6 ore fino a +120h, poi ogni 12 ore fino a `last`."""
    return list(range(0, 121, 6)) + list(range(132, last + 1, 12))


MODELS = {
    "gfs":   {"label": "GFS",   "org": "NOAA",  "res": "0.25°",              "steps": _steps(384)},
    "ecmwf": {"label": "ECMWF", "org": "ECMWF", "res": "0.25°",              "steps": _steps(360)},
    "icon":  {"label": "ICON",  "org": "DWD",   "res": "13 km (globale)",    "steps": _steps(180)},
}

# Aree disegnate: estensione [lon_min, lon_max, lat_min, lat_max] e centro della proiezione
AREAS = {
    "it": {"label": "Italia", "extent": [5.0, 20.5, 35.5, 47.8], "center": (12.5, 42.0)},
    "eu": {"label": "Europa", "extent": [-22.0, 40.0, 33.0, 68.0], "center": (9.0, 50.0)},
    "am": {"label": "Nord America", "extent": [-135.0, -55.0, 15.0, 60.0], "center": (-95.0, 40.0)},
    "nh": {"label": "Emisfero N", "extent": [-180.0, 180.0, 20.0, 90.0], "center": (10.0, 90.0)},
}

# Mappe disponibili e campi necessari
MAPS = {
    "z500":  {"label": "Geopotenziale 500 hPa + T 850 hPa", "short": "500 hPa", "needs": ["z500", "t850"]},
    "t850":  {"label": "Termiche a 850 hPa",                 "short": "T 850",   "needs": ["t850"]},
    "pcp":   {"label": "Pressione al suolo + pioggia 6 h",  "short": "Pioggia",  "needs": ["mslp", "tp6"]},
    "t2m":   {"label": "Temperatura a 2 m",                  "short": "Temp. 2 m", "needs": ["t2m"]},
    "vento": {"label": "Vento a 10 m",                       "short": "Vento",   "needs": ["u10", "v10"]},
    "cape":  {"label": "CAPE (energia per temporali)",       "short": "CAPE",    "needs": ["cape"], "areas": ["it", "eu"]},
}

CREDITS = {
    "gfs": "Dati: NOAA/NCEP GFS",
    "ecmwf": "Dati: ECMWF Open Data (CC BY 4.0)",
    "icon": "Dati: Deutscher Wetterdienst (ICON globale)",
}
