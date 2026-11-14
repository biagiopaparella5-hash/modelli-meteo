"""Download e decodifica dei dati GRIB di GFS, ECMWF e ICON-EU.

Ogni funzione `fetch_<modello>` restituisce (run_datetime_utc, {step: {campo: Field}})
dove i campi sono già ritagliati sulla REGION e convertiti in unità "umane":
  z500 dam, t850 °C, mslp hPa, tp6 mm (ultime 6 h), t2m °C, u10/v10 m/s, cape J/kg
"""
from __future__ import annotations

import bz2
import datetime as dt
import os
import tempfile
import time
from dataclasses import dataclass

import numpy as np
import requests

from config import REGION

UTC = dt.timezone.utc
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "modelli-meteo-app/1.0 (github actions)"


@dataclass
class Field:
    lats: np.ndarray   # 1D crescente
    lons: np.ndarray   # 1D crescente, -180..180
    data: np.ndarray   # 2D [lat, lon] float32


# --------------------------------------------------------------------------- GRIB
def read_grib(path: str) -> list[dict]:
    """Legge tutti i messaggi di un file GRIB (griglie lat/lon regolari)."""
    import eccodes as ec

    out = []
    with open(path, "rb") as f:
        while True:
            gid = ec.codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                ni = ec.codes_get(gid, "Ni")
                nj = ec.codes_get(gid, "Nj")
                lat1 = ec.codes_get(gid, "latitudeOfFirstGridPointInDegrees")
                lat2 = ec.codes_get(gid, "latitudeOfLastGridPointInDegrees")
                lon1 = ec.codes_get(gid, "longitudeOfFirstGridPointInDegrees")
                di = ec.codes_get(gid, "iDirectionIncrementInDegrees")
                vals = ec.codes_get_values(gid).reshape(nj, ni).astype(np.float32)
                missing = ec.codes_get(gid, "missingValue")
                vals[vals == missing] = np.nan
                msg = {
                    "shortName": ec.codes_get(gid, "shortName"),
                    "typeOfLevel": ec.codes_get(gid, "typeOfLevel"),
                    "level": ec.codes_get(gid, "level"),
                    "stepRange": str(ec.codes_get(gid, "stepRange")),
                    "step": ec.codes_get(gid, "endStep"),
                }
                lats = np.linspace(lat1, lat2, nj)
                lons = lon1 + np.arange(ni) * di
                msg["field"] = _normalize(lats, lons, vals)
                out.append(msg)
            finally:
                ec.codes_release(gid)
    return out


def _normalize(lats, lons, vals) -> Field:
    lons = ((lons + 180.0) % 360.0) - 180.0
    order = np.argsort(lons, kind="stable")
    lons, vals = lons[order], vals[:, order]
    if lats[0] > lats[-1]:
        lats, vals = lats[::-1], vals[::-1, :]
    r = REGION
    jy = (lats >= r["lat_min"] - 0.5) & (lats <= r["lat_max"] + 0.5)
    ix = (lons >= r["lon_min"] - 0.5) & (lons <= r["lon_max"] + 0.5)
    return Field(lats[jy].astype(np.float32), lons[ix].astype(np.float32),
                 np.ascontiguousarray(vals[np.ix_(jy, ix)]))


def _get(url: str, dest: str, tries: int = 4, timeout: int = 120) -> bool:
    for k in range(tries):
        try:
            r = SESSION.get(url, timeout=timeout, stream=True)
            if r.status_code == 404:
                return False
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            return True
        except Exception as e:  # rete instabile: riprova
            print(f"  ! {url} -> {e} (tentativo {k + 1})")
            time.sleep(3 * (k + 1))
    return False


def _exists(url: str) -> bool:
    try:
        r = SESSION.head(url, timeout=30, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


def _candidate_runs(now: dt.datetime, every: int, delay_h: float, n: int = 5):
    t = now - dt.timedelta(hours=delay_h)
    t = t.replace(minute=0, second=0, microsecond=0)
    t = t.replace(hour=(t.hour // every) * every)
    for k in range(n):
        yield t - dt.timedelta(hours=every * k)


# --------------------------------------------------------------------------- GFS
GFS_FILE = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.{d}/{h}/atmos/gfs.t{h}z.pgrb2.0p25.f{s:03d}"
GFS_FILTER = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"


def fetch_gfs(steps, workdir):
    now = dt.datetime.now(UTC)
    run = None
    for cand in _candidate_runs(now, 6, 3.5):
        if _exists(GFS_FILE.format(d=f"{cand:%Y%m%d}", h=f"{cand:%H}", s=max(steps))):
            run = cand
            break
    if run is None:
        raise RuntimeError("Nessuna corsa GFS completa trovata")
    print(f"GFS: corsa {run:%Y-%m-%d %HZ}")
    out = {}
    for s in steps:
        params = {
            "dir": f"/gfs.{run:%Y%m%d}/{run:%H}/atmos",
            "file": f"gfs.t{run:%H}z.pgrb2.0p25.f{s:03d}",
            "var_HGT": "on", "var_TMP": "on", "var_PRMSL": "on", "var_APCP": "on",
            "var_UGRD": "on", "var_VGRD": "on", "var_CAPE": "on",
            "lev_500_mb": "on", "lev_850_mb": "on", "lev_mean_sea_level": "on",
            "lev_surface": "on", "lev_2_m_above_ground": "on", "lev_10_m_above_ground": "on",
            "subregion": "", "toplat": 73, "bottomlat": 24, "leftlon": -36, "rightlon": 51,
        }
        url = GFS_FILTER + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        dest = os.path.join(workdir, f"gfs_{s:03d}.grb2")
        if not _get(url, dest):
            print(f"  GFS +{s}h non disponibile")
            continue
        time.sleep(0.6)  # rispetta i limiti di NOMADS
        f = {}
        for m in read_grib(dest):
            sn, tl, lv, fld = m["shortName"], m["typeOfLevel"], m["level"], m["field"]
            if sn == "gh" and lv == 500 and tl == "isobaricInhPa":
                f["z500"] = _scale(fld, 0.1)                 # gpm -> dam
            elif sn == "t" and lv == 850 and tl == "isobaricInhPa":
                f["t850"] = _scale(fld, 1, -273.15)
            elif sn == "prmsl":
                f["mslp"] = _scale(fld, 0.01)
            elif sn == "2t":
                f["t2m"] = _scale(fld, 1, -273.15)
            elif sn == "10u":
                f["u10"] = fld
            elif sn == "10v":
                f["v10"] = fld
            elif sn == "cape" and tl == "surface":
                f["cape"] = fld
            elif sn == "tp":
                a, _, b = m["stepRange"].partition("-")
                if b and int(b) - int(a) == 6:
                    f["tp6"] = fld
        if s == 0 and "mslp" in f:
            f["tp6"] = _zeros_like(f["mslp"])
        out[s] = f
        os.remove(dest)
    return run, out


# --------------------------------------------------------------------------- ECMWF
def fetch_ecmwf(steps, workdir):
    from ecmwf.opendata import Client

    client = Client(source="ecmwf", model="ifs", resol="0p25")
    run = client.latest(type="fc", step=max(steps), param="msl")
    run = run.replace(tzinfo=UTC)
    print(f"ECMWF: corsa {run:%Y-%m-%d %HZ}")
    # serve anche tp a step-6 per calcolare la pioggia delle ultime 6 h
    tp_steps = sorted(set(steps) | {s - 6 for s in steps if s >= 6})
    common = dict(date=run.strftime("%Y%m%d"), time=run.hour, type="fc", stream="oper")

    pl = os.path.join(workdir, "ec_pl.grb2")
    sfc = os.path.join(workdir, "ec_sfc.grb2")
    tpf = os.path.join(workdir, "ec_tp.grb2")
    client.retrieve(**common, step=steps, levtype="pl", levelist=[500, 850], param=["gh", "t"], target=pl)
    client.retrieve(**common, step=steps, levtype="sfc", param=["msl", "2t", "10u", "10v"], target=sfc)
    client.retrieve(**common, step=tp_steps, levtype="sfc", param="tp", target=tpf)

    out = {s: {} for s in steps}
    for m in read_grib(pl) + read_grib(sfc):
        s, sn, lv, fld = m["step"], m["shortName"], m["level"], m["field"]
        if s not in out:
            continue
        if sn == "gh" and lv == 500:
            out[s]["z500"] = _scale(fld, 0.1)
        elif sn == "t" and lv == 850:
            out[s]["t850"] = _scale(fld, 1, -273.15)
        elif sn == "msl":
            out[s]["mslp"] = _scale(fld, 0.01)
        elif sn == "2t":
            out[s]["t2m"] = _scale(fld, 1, -273.15)
        elif sn == "10u":
            out[s]["u10"] = fld
        elif sn == "10v":
            out[s]["v10"] = fld
    tp = {m["step"]: m["field"] for m in read_grib(tpf) if m["shortName"] == "tp"}
    for s in steps:
        if s == 0 and "mslp" in out[s]:
            out[s]["tp6"] = _zeros_like(out[s]["mslp"])
        elif s in tp and (s - 6) in tp:
            out[s]["tp6"] = _diff(tp[s], tp[s - 6], 1000.0)   # m -> mm
    for p in (pl, sfc, tpf):
        os.remove(p)
    return run, out


# --------------------------------------------------------------------------- ICON-EU
ICON_URL = ("https://opendata.dwd.de/weather/nwp/icon-eu/grib/{h}/{var_l}/"
            "icon-eu_europe_regular-lat-lon_{kind}_{run}_{s:03d}_{lev}{VAR}.grib2.bz2")

ICON_VARS = {  # nostro nome: (VAR, tipo, livello)
    "z500": ("FI", "pressure-level", 500),
    "t850": ("T", "pressure-level", 850),
    "mslp": ("PMSL", "single-level", None),
    "t2m": ("T_2M", "single-level", None),
    "u10": ("U_10M", "single-level", None),
    "v10": ("V_10M", "single-level", None),
    "cape": ("CAPE_ML", "single-level", None),
    "tot": ("TOT_PREC", "single-level", None),
}


def _icon_url(run, name, s):
    var, kind, lev = ICON_VARS[name]
    return ICON_URL.format(h=f"{run:%H}", var_l=var.lower(), kind=kind, run=f"{run:%Y%m%d%H}",
                           s=s, lev=f"{lev}_" if lev else "", VAR=var)


def fetch_icon(steps, workdir):
    now = dt.datetime.now(UTC)
    run = None
    for cand in _candidate_runs(now, 6, 3.0):
        if _exists(_icon_url(cand, "mslp", max(steps))):
            run = cand
            break
    if run is None:
        raise RuntimeError("Nessuna corsa ICON-EU completa trovata")
    print(f"ICON-EU: corsa {run:%Y-%m-%d %HZ}")

    def load(name, s):
        dest = os.path.join(workdir, f"icon_{name}_{s:03d}.grb2")
        tmp = dest + ".bz2"
        if not _get(_icon_url(run, name, s), tmp):
            return None
        with open(tmp, "rb") as fi, open(dest, "wb") as fo:
            fo.write(bz2.decompress(fi.read()))
        os.remove(tmp)
        msgs = read_grib(dest)
        os.remove(dest)
        return msgs[0]["field"] if msgs else None

    out = {}
    tot_prev = None
    for s in steps:
        f = {}
        for name in ("z500", "t850", "mslp", "t2m", "u10", "v10", "cape"):
            fld = load(name, s)
            if fld is None:
                continue
            if name == "z500":
                fld = _scale(fld, 1 / 98.0665)             # m2/s2 -> dam
            elif name in ("t850", "t2m"):
                fld = _scale(fld, 1, -273.15)
            elif name == "mslp":
                fld = _scale(fld, 0.01)
            f[name] = fld
        tot = load("tot", s)
        if s == 0 and "mslp" in f:
            f["tp6"] = _zeros_like(f["mslp"])
        elif tot is not None and tot_prev is not None:
            f["tp6"] = _diff(tot, tot_prev, 1.0)
        tot_prev = tot
        out[s] = f
    return run, out


# --------------------------------------------------------------------------- utilità
def _scale(f: Field, k, add=0.0) -> Field:
    return Field(f.lats, f.lons, (f.data * k + add).astype(np.float32))


def _diff(a: Field, b: Field, k) -> Field:
    return Field(a.lats, a.lons, np.clip((a.data - b.data) * k, 0, None).astype(np.float32))


def _zeros_like(f: Field) -> Field:
    return Field(f.lats, f.lons, np.zeros_like(f.data))


FETCHERS = {"gfs": fetch_gfs, "ecmwf": fetch_ecmwf, "icon": fetch_icon}
