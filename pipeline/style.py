"""Stile grafico delle mappe: palette, intestazioni, disegno dei campi."""
from __future__ import annotations

import datetime as dt
import io
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image
from scipy import ndimage

from config import AREAS, CREDITS, MAPS, MODELS

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
    PC = ccrs.PlateCarree()
except ImportError:  # solo per i test locali senza cartopy
    HAS_CARTOPY = False
    PC = None

ROME = ZoneInfo("Europe/Rome")
BG = "#0b1220"
FG = "#e8eef8"
MUTED = "#8b9ab3"
MODEL_COLORS = {"gfs": "#4f8cff", "ecmwf": "#22c55e", "icon": "#f59e0b"}
GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": FG,
    "axes.edgecolor": BG,
})


def _cmap(colors, name, n=256):
    return LinearSegmentedColormap.from_list(name, colors, N=n)


TEMP_COLORS = ["#2b0b4f", "#3a2c94", "#2f5fd1", "#2f95e6", "#5fcde4", "#a7ecd6",
               "#eef3b4", "#f8d36e", "#f39b45", "#e5582f", "#bb2441", "#6e0b44"]
CMAP_TEMP = _cmap(TEMP_COLORS, "temp")
CMAP_WIND = _cmap(["#1d3557", "#1f6f8b", "#22a39f", "#7ccf8a", "#e9e46b", "#f6a44c",
                   "#e85b46", "#c22a6a", "#7d1d9c", "#e9d5ff"], "wind")
PCP_LEVELS = [0.2, 0.5, 1, 2, 4, 6, 10, 15, 20, 30, 40, 60, 80, 100]
PCP_COLORS = ["#a5e9ff", "#6fd0fb", "#3fa9f5", "#2f7de1", "#2b55c2", "#4834b0", "#7b2fb8",
              "#a92fb3", "#d63a9c", "#f2557a", "#ff8a5c", "#ffc15c", "#fff2a8"]
CAPE_LEVELS = [100, 250, 500, 750, 1000, 1500, 2000, 2500, 3000, 4000]
CAPE_COLORS = ["#3b7d5a", "#68a948", "#b5cf3d", "#f2d43b", "#f5a53a", "#ef6c33",
               "#d9333f", "#b0216e", "#7d1f9e", "#c9a3ff"]

HALO = [pe.withStroke(linewidth=2.6, foreground="#0b1220c0")]


# --------------------------------------------------------------------------- base
def _new_map(area_id):
    area = AREAS[area_id]
    fig = plt.figure(figsize=(9.6, 9.6), dpi=112, facecolor=BG)
    rect = [0.015, 0.115, 0.97, 0.775]
    if HAS_CARTOPY:
        lon0, lat0 = area["center"]
        proj = ccrs.LambertConformal(central_longitude=lon0, central_latitude=lat0,
                                     standard_parallels=(lat0 - 8, lat0 + 8))
        ax = fig.add_axes(rect, projection=proj)
        ax.set_extent(area["extent"], crs=PC)
        ax.set_facecolor("#0e1726")
        ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="#182235", edgecolor="none", zorder=0)
        ax.spines["geo"].set_edgecolor("#26324a")
    else:
        ax = fig.add_axes(rect)
        e = area["extent"]
        ax.set_xlim(e[0], e[1]); ax.set_ylim(e[2], e[3])
        ax.set_facecolor("#0e1726")
        ax.set_xticks([]); ax.set_yticks([])
    return fig, ax


def _tr():
    return {"transform": PC} if HAS_CARTOPY else {}


def _geo(ax):
    if HAS_CARTOPY:
        ax.add_feature(cfeature.COASTLINE.with_scale("50m"), edgecolor="#e8eef8", linewidth=0.7, alpha=0.85, zorder=5)
        ax.add_feature(cfeature.BORDERS.with_scale("50m"), edgecolor="#e8eef8", linewidth=0.45, alpha=0.5, zorder=5)
        gl = ax.gridlines(draw_labels=False, linewidth=0.3, color="#ffffff", alpha=0.12, linestyle="-")
        gl.zorder = 4


def _crop(f, area_id, pad=3.0):
    e = AREAS[area_id]["extent"]
    jy = (f.lats >= e[2] - pad) & (f.lats <= e[3] + pad)
    ix = (f.lons >= e[0] - pad * 2) & (f.lons <= e[1] + pad * 2)
    return f.lons[ix], f.lats[jy], f.data[np.ix_(jy, ix)]


def _res(lons):
    return float(abs(lons[1] - lons[0])) if len(lons) > 1 else 0.25


def _smooth(data, lons, deg=0.5):
    s = max(deg / _res(lons), 0.5)
    d = np.where(np.isnan(data), np.nanmean(data), data)
    return ndimage.gaussian_filter(d, s)


# --------------------------------------------------------------------------- testo
def _fmt_local(t: dt.datetime):
    lt = t.astimezone(ROME)
    return f"{GIORNI[lt.weekday()]} {lt:%d/%m} ore {lt:%H:%M}"


def _header(fig, model, map_id, run, step):
    color = MODEL_COLORS[model]
    label = MODELS[model]["label"]
    fig.patches.append(FancyBboxPatch((0.03, 0.935), 0.105, 0.042, boxstyle="round,pad=0.004,rounding_size=0.012",
                                      transform=fig.transFigure, facecolor=color, edgecolor="none"))
    fig.text(0.0825, 0.956, label, ha="center", va="center", fontsize=15, fontweight="bold", color="#0b1220")
    fig.text(0.155, 0.956, MAPS[map_id]["label"], ha="left", va="center", fontsize=15, fontweight="bold", color=FG)
    valid = run + dt.timedelta(hours=step)
    run_txt = f"Corsa {GIORNI[run.weekday()]} {run:%d/%m %H} UTC"
    fig.text(0.03, 0.908, f"{run_txt}   ·   Valida {_fmt_local(valid)}", ha="left", va="center",
             fontsize=11.5, color=MUTED)
    fig.text(0.97, 0.956, f"+{step}h", ha="right", va="center", fontsize=22, fontweight="bold", color=color)


def _footer(fig, model, unit_label):
    fig.text(0.03, 0.022, CREDITS[model], ha="left", va="center", fontsize=9, color=MUTED)
    fig.text(0.97, 0.022, "Modelli Meteo", ha="right", va="center", fontsize=9, color=MUTED, fontweight="bold")
    fig.text(0.5, 0.098, unit_label, ha="center", va="center", fontsize=10, color=MUTED)


def _colorbar(fig, mappable, ticks=None):
    cax = fig.add_axes([0.08, 0.055, 0.84, 0.022])
    cb = fig.colorbar(mappable, cax=cax, orientation="horizontal", ticks=ticks, drawedges=False, format="%g")
    cb.outline.set_visible(False)
    cax.tick_params(colors=FG, labelsize=9, length=0, pad=3)
    return cb


# --------------------------------------------------------------------------- mappe
def _draw_z500(ax, fig, fl, area_id):
    lon, lat, t = _crop(fl["t850"], area_id)
    levels = np.arange(-30, 31, 2)
    cf = ax.contourf(lon, lat, np.clip(t, -30, 30), levels=levels, cmap=CMAP_TEMP, extend="both", zorder=1, **_tr())
    lon, lat, z = _crop(fl["z500"], area_id)
    z = _smooth(z, lon, 0.6)
    zl = np.arange(480, 604, 4)
    cs = ax.contour(lon, lat, z, levels=zl, colors="#ffffff", linewidths=1.1, zorder=6, **_tr())
    for c in _collections(cs):
        c.set_path_effects([pe.withStroke(linewidth=2.0, foreground="#0b122055")])
    lbl = ax.clabel(cs, fmt="%d", fontsize=8.5, inline=True, inline_spacing=3)
    for t_ in lbl:
        t_.set_path_effects(HALO); t_.set_color("#ffffff")
    _colorbar(fig, cf, ticks=levels[::2])
    return "Temperatura a 850 hPa (°C)  ·  linee: geopotenziale 500 hPa (dam)"


def _draw_pcp(ax, fig, fl, area_id):
    cf = None
    if "tp6" in fl:
        lon, lat, p = _crop(fl["tp6"], area_id)
        cmap = ListedColormap(PCP_COLORS); cmap.set_over("#ffffff")
        norm = BoundaryNorm(PCP_LEVELS, cmap.N)
        cf = ax.contourf(lon, lat, p, levels=PCP_LEVELS, cmap=cmap, norm=norm, extend="max", alpha=0.92, zorder=2, **_tr())
    lon, lat, m = _crop(fl["mslp"], area_id)
    ms = _smooth(m, lon, 0.5)
    cs = ax.contour(lon, lat, ms, levels=np.arange(940, 1061, 4), colors="#ffffff", linewidths=0.9, alpha=0.95, zorder=6, **_tr())
    lbl = ax.clabel(cs, fmt="%d", fontsize=8, inline=True, inline_spacing=2)
    for t_ in lbl:
        t_.set_path_effects(HALO); t_.set_color("#ffffff")
    _highs_lows(ax, lon, lat, ms, area_id)
    if cf is not None:
        _colorbar(fig, cf, ticks=PCP_LEVELS)
    return "Pioggia nelle ultime 6 ore (mm)  ·  linee: pressione al livello del mare (hPa)"


def _highs_lows(ax, lon, lat, m, area_id):
    e = AREAS[area_id]["extent"]
    size = max(int(round(7.0 / _res(lon))), 3)
    mx = ndimage.maximum_filter(m, size=size, mode="nearest")
    mn = ndimage.minimum_filter(m, size=size, mode="nearest")
    for mask, letter, color in ((m == mx, "A", "#60a5fa"), (m == mn, "B", "#f87171")):
        jj, ii = np.nonzero(mask)
        found = []
        for j, i in zip(jj, ii):
            x, y, v = lon[i], lat[j], m[j, i]
            if not (e[0] + 1 < x < e[1] - 1 and e[2] + 1 < y < e[3] - 1):
                continue
            if letter == "A" and v < 1015 or letter == "B" and v > 1010:
                continue
            if any(abs(x - a) < 4 and abs(y - b) < 4 for a, b in found):
                continue
            found.append((x, y))
            ax.text(x, y, letter, ha="center", va="center", fontsize=20, fontweight="bold", color=color,
                    path_effects=HALO, zorder=8, **_tr())
            ax.text(x, y - 0.9 * (e[3] - e[2]) / 30, f"{v:.0f}", ha="center", va="top", fontsize=8.5,
                    color=color, path_effects=HALO, zorder=8, **_tr())


def _draw_t2m(ax, fig, fl, area_id):
    lon, lat, t = _crop(fl["t2m"], area_id)
    levels = np.arange(-20, 41, 2)
    cf = ax.contourf(lon, lat, np.clip(t, -20, 40), levels=levels, cmap=CMAP_TEMP, extend="both", zorder=1, **_tr())
    cs = ax.contour(lon, lat, _smooth(t, lon, 0.3), levels=[0], colors="#ffffff", linewidths=0.8,
                    linestyles="--", alpha=0.7, zorder=6, **_tr())
    _colorbar(fig, cf, ticks=levels[::2])
    return "Temperatura a 2 m dal suolo (°C)  ·  tratteggio: linea dello zero"


def _draw_vento(ax, fig, fl, area_id):
    lon, lat, u = _crop(fl["u10"], area_id)
    _, _, v = _crop(fl["v10"], area_id)
    spd = np.hypot(u, v) * 3.6
    levels = np.arange(0, 131, 5)
    cf = ax.contourf(lon, lat, np.clip(spd, 0, 130), levels=levels, cmap=CMAP_WIND, extend="max", zorder=1, **_tr())
    if HAS_CARTOPY:
        ax.quiver(lon, lat, u, v, transform=PC, regrid_shape=24, color="#ffffff", alpha=0.85,
                  scale=None, width=0.0022, headwidth=4, zorder=6)
    else:
        st = max(len(lon) // 24, 1)
        ax.quiver(lon[::st], lat[::st], u[::st, ::st], v[::st, ::st], color="#ffffff", alpha=0.85, width=0.0022, zorder=6)
    _colorbar(fig, cf, ticks=levels[::2])
    return "Velocità del vento a 10 m (km/h)  ·  frecce: direzione"


def _draw_cape(ax, fig, fl, area_id):
    lon, lat, c = _crop(fl["cape"], area_id)
    cmap = ListedColormap(CAPE_COLORS[:-1]); cmap.set_over(CAPE_COLORS[-1])
    norm = BoundaryNorm(CAPE_LEVELS, cmap.N)
    cf = ax.contourf(lon, lat, c, levels=CAPE_LEVELS, cmap=cmap, norm=norm, extend="max", alpha=0.9, zorder=2, **_tr())
    if "mslp" in fl:
        lon, lat, m = _crop(fl["mslp"], area_id)
        ax.contour(lon, lat, _smooth(m, lon, 0.5), levels=np.arange(940, 1061, 4), colors="#ffffff",
                   linewidths=0.6, alpha=0.55, zorder=6, **_tr())
    _colorbar(fig, cf, ticks=CAPE_LEVELS)
    return "CAPE (J/kg): energia disponibile per i temporali  ·  linee: pressione (hPa)"


def _collections(cs):
    return getattr(cs, "collections", None) or [cs]


DRAW = {"z500": _draw_z500, "pcp": _draw_pcp, "t2m": _draw_t2m, "vento": _draw_vento, "cape": _draw_cape}


def render_map(fields, model, map_id, area_id, run, step, out_path):
    fig, ax = _new_map(area_id)
    try:
        unit = DRAW[map_id](ax, fig, fields, area_id)
        _geo(ax)
        _header(fig, model, map_id, run, step)
        _footer(fig, model, unit)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor=BG, dpi=112)
    finally:
        plt.close(fig)
    buf.seek(0)
    img = Image.open(buf).convert("RGB").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    img.save(out_path, optimize=True)
