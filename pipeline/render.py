"""Scarica gli ultimi run dei modelli e genera mappe + manifest.json nella cartella di output.

Uso:
  python render.py --out ../site                 # tutti i modelli
  python render.py --out ../site --models gfs    # solo GFS
  python render.py --out ../site --test          # dati sintetici, senza rete (prova grafica)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

from config import AREAS, MAPS, MODELS
from sources import FETCHERS, Field
import style

UTC = dt.timezone.utc


def save_step(path, fields):
    arrs = {}
    for name, f in fields.items():
        arrs[f"{name}__d"] = f.data
        arrs[f"{name}__y"] = f.lats
        arrs[f"{name}__x"] = f.lons
    np.savez(path, **arrs)


def load_step(path):
    z = np.load(path)
    names = {k.split("__")[0] for k in z.files}
    return {n: Field(z[f"{n}__y"], z[f"{n}__x"], z[f"{n}__d"]) for n in names}


def render_step(model, step, run_iso, npz, out_dir):
    run = dt.datetime.fromisoformat(run_iso)
    fields = load_step(npz)
    done = []
    for map_id, spec in MAPS.items():
        if not all(n in fields for n in spec["needs"]):
            continue
        for area_id in spec.get("areas", AREAS):
            d = os.path.join(out_dir, "maps", model, area_id, map_id)
            os.makedirs(d, exist_ok=True)
            try:
                style.render_map(fields, model, map_id, area_id, run, step, os.path.join(d, f"{step:03d}.png"))
                done.append((map_id, area_id))
            except Exception:
                print(f"  ! errore {model} {map_id} {area_id} +{step}h")
                traceback.print_exc()
    return model, step, done


def prewarm_cartopy():
    """Scarica coste/confini una sola volta, prima dei processi paralleli (evita file corrotti)."""
    if not style.HAS_CARTOPY:
        return
    import cartopy.feature as cf
    for feat in (cf.LAND, cf.COASTLINE, cf.BORDERS):
        for sc in ("50m", "110m"):
            list(feat.with_scale(sc).geometries())
    list(cf.NaturalEarthFeature("cultural", "admin_1_states_provinces_lines", "10m").geometries())


def synthetic(model, steps):
    """Campi finti ma realistici per provare la grafica senza rete."""
    lats = np.arange(-5, 90.01, 0.5, dtype=np.float32)
    lons = np.arange(-180, 180, 0.5, dtype=np.float32)
    X, Y = np.meshgrid(lons, lats)
    out = {}
    for s in steps:
        ph = s / 24.0
        cx, cy = -5 + 3 * ph, 50 - 0.5 * ph
        low = np.exp(-(((X - cx) / 9) ** 2 + ((Y - cy) / 6) ** 2))
        high = np.exp(-(((X - 25 + ph) / 12) ** 2 + ((Y - 40) / 8) ** 2))
        wave = np.sin((X + 4 * ph) / 9) * np.cos((Y - 45) / 10)
        f = lambda a: Field(lats, lons, a.astype(np.float32))
        z = 588 - (Y - 30) * 1.7 - 18 * low + 8 * high + 3 * wave
        t850 = 22 - (Y - 30) * 0.75 - 8 * low + 5 * high + 2 * wave
        mslp = 1013 - 28 * low + 16 * high + 3 * wave
        gy, gx = np.gradient(mslp)
        u, v = gy * 9, -gx * 9
        out[s] = {
            "z500": f(z), "t850": f(t850), "mslp": f(mslp),
            "t2m": f(t850 + 9 + 3 * np.sin(X / 3)),
            "tp6": f(np.clip(40 * low * (0.5 + 0.5 * np.sin(X / 2 + Y / 3)) - 2, 0, None)),
            "u10": f(u), "v10": f(v),
            "cape": f(np.clip(2500 * high * (0.5 + 0.5 * np.cos(X / 2)) - 200, 0, None)),
        }
        if model == "ecmwf":
            out[s].pop("cape")
    return dt.datetime(2026, 11, 13, 0, tzinfo=UTC), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../site")
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--steps", default="", help="solo per test: es. 0,24")
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="meteo_")
    manifest = {"generated": dt.datetime.now(UTC).isoformat(timespec="minutes"),
                "areas": {k: v["label"] for k, v in AREAS.items()},
                "maps": {k: {"label": v["label"], "short": v["short"]} for k, v in MAPS.items()},
                "models": {}}

    import time
    t0 = time.time()
    tasks = []
    for model in args.models.split(","):
        steps = MODELS[model]["steps"]
        if args.steps:
            steps = [int(s) for s in args.steps.split(",")]
        try:
            os.makedirs(os.path.join(work, model), exist_ok=True)
            if args.test:
                run, data = synthetic(model, steps)
            else:
                run, data = FETCHERS[model](steps, os.path.join(work, model))
        except Exception:
            print(f"!! {model}: download fallito, salto il modello")
            traceback.print_exc()
            continue
        manifest["models"][model] = {**{k: MODELS[model][k] for k in ("label", "org", "res")},
                                     "run": run.isoformat(), "maps": {}}
        for s, fields in data.items():
            if not fields:
                continue
            npz = os.path.join(work, model, f"{s:03d}.npz")
            save_step(npz, fields)
            tasks.append((model, s, run.isoformat(), npz))
        del data

    prewarm_cartopy()
    t1 = time.time()
    print(f"Disegno {len(tasks)} scadenze con {args.workers} processi…")
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(render_step, *t, out_dir) for t in tasks]
        for fu in as_completed(futs):
            model, step, done = fu.result()
            maps = manifest["models"][model]["maps"]
            for map_id, area_id in done:
                maps.setdefault(map_id, {}).setdefault(area_id, []).append(step)

    manifest["timing"] = {"download_min": round((t1 - t0) / 60, 1), "render_min": round((time.time() - t1) / 60, 1)}
    for m in manifest["models"].values():
        for areas in m["maps"].values():
            for a in areas:
                areas[a].sort()
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
    shutil.rmtree(work, ignore_errors=True)
    n = sum(len(v) for m in manifest["models"].values() for a in m["maps"].values() for v in a.values())
    print(f"Fatto: {n} mappe. Modelli: {', '.join(manifest['models']) or 'nessuno'}")
    if not manifest["models"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
