#!/usr/bin/env python3
"""Final walk metrics, sampled at the DEM's own resolution.

The spacing sweep in fwh-dem-test.py showed cumulative gain does not converge as
spacing shrinks (467m at 300m spacing rising to 1598m at 25m on the same track),
which is the signature of summing DEM noise rather than measuring terrain.
Open-Meteo serves a roughly 90m model, so anything finer interpolates noise.

So: sample at 100m, at the model's own resolution, and treat gain as approximate.
Distance and the altitude range are robust and are not affected by this.
"""
import json, math, time, urllib.request, urllib.parse
from nztm import nztm_to_wgs84

STEP_M = 100.0
R = 6371.0088

def hav(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    x = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(x))

def length_km(pts):
    return sum(hav(pts[i], pts[i + 1]) for i in range(len(pts) - 1))

def densify(pts, step_m=STEP_M):
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]; carry = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = hav(a, b) * 1000.0
        if seg <= 0:
            continue
        t = step_m - carry
        while t <= seg:
            f = t / seg
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            t += step_m
        carry = (carry + seg) % step_m
    if out[-1] != pts[-1]:
        out.append(pts[-1])
    return out

def elevations(pts):
    out = []
    for i in range(0, len(pts), 100):
        c = pts[i:i + 100]
        url = ("https://api.open-meteo.com/v1/elevation?latitude="
               + ",".join(f"{p[0]:.6f}" for p in c)
               + "&longitude=" + ",".join(f"{p[1]:.6f}" for p in c))
        for a in range(6):
            try:
                with urllib.request.urlopen(url, timeout=90) as f:
                    out += json.load(f)["elevation"]
                break
            except Exception as e:
                if a == 5:
                    raise
                print(f"    [retry {a+1}: {e}]", flush=True)
                time.sleep(5 + a * 5)
        time.sleep(1.2)
    return out

# Flat-water control was run once and returned 0.0 m of gain at both 100m and 25m
# spacing. That only proves the API is deterministic, not that terrain sampling is
# clean: DEMs flatten lakes hydrologically, so a lake cannot show the artefact.
# The real evidence is non-convergence over actual terrain, in fwh-dem-test.py.

EPS = ["https://overpass-api.de/api/interpreter",
       "https://overpass.kumi.systems/api/interpreter"]

def overpass(q):
    for ep in EPS:
        try:
            req = urllib.request.Request(
                ep, data=urllib.parse.urlencode({"data": q}).encode(),
                headers={"User-Agent": "fwh-trip-map/1.0"})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)
        except Exception as e:
            print(f"    [overpass fail {ep}: {e}]", flush=True)
            time.sleep(4)
    return None

WALKS = [
    ("Cardiff Walkway",       "osm", None, -39.360070, 174.228620, "Cardiff Walkway", "Loop"),
    ("Carrington Walkway",    "osm", None, -39.341805, 174.287234, "Carrington Walkway", "Walkway network"),
    ("Moki Track",            "doc", "Moki Track", -38.976716, 174.746371, None, "One way"),
    ("Mount Damper Falls",    "doc", "Mount Damper Falls Walk", -38.920083, 174.787198, None, "Return"),
    ("Joshua Morgan's Grave", "osm", None, -38.978183, 174.834023, None, "Return"),
    ("Tatu Track",            "osm", None, -38.906898, 174.913255, "Tatu Track", "Return"),
    ("Aukopae Tunnel walk",   "osm", None, -38.925692, 175.083999, "Aukopae Tunnel walk", "Return"),
    ("Te Maire Loop Track",   "doc", "Te Maire Loop Track", -38.951636, 175.187138, None, "Loop"),
    ("Ohinetonga Track",      "doc", "Ohinetonga Track", -38.992277, 175.394658, None, "Loop"),
    ("Taumarunui River Walk", "osm", None, -38.884380, 175.257257, "River walking trail", "Return"),
]

doc = {t["name"]: t for t in json.load(open("/tmp/doc-tracks.json"))}
out = {}
print("\nwalks, sampled at 100 m:\n", flush=True)

for name, src, dockey, lat, lon, osmname, shape in WALKS:
    ways, tags = [], {}
    if src == "doc":
        for seg in doc[dockey]["line"]:
            ways.append([nztm_to_wgs84(x, y) for x, y in seg])
        srclabel = "DOC:" + dockey
    else:
        q = (f'[out:json][timeout:180];'
             f'way["highway"~"^(path|footway|track|steps)$"](around:700,{lat},{lon});'
             f'out geom tags;')
        d = overpass(q)
        if not d:
            print(f"{name}: NO OVERPASS DATA"); continue
        for el in d.get("elements", []):
            g = el.get("geometry")
            if not g:
                continue
            nm = (el.get("tags") or {}).get("name") or "(unnamed)"
            if osmname and nm != osmname:
                continue
            if not osmname and nm != "(unnamed)":
                continue
            pts = [(p["lat"], p["lon"]) for p in g]
            if not osmname and min(hav((lat, lon), p) for p in pts) > 0.12:
                continue
            ways.append(pts)
            for k in ("surface", "sac_scale", "access", "foot", "informal", "incline"):
                if k in (el.get("tags") or {}):
                    tags[k] = el["tags"][k]
        srclabel = "OSM:" + (osmname or "unnamed spur")
        time.sleep(1.5)

    if not ways:
        print(f"{name}: NO GEOMETRY"); continue

    one_way_km = sum(length_km(w) for w in ways)
    gain = loss = 0.0; los = []; his = []; nsamp = 0
    for w in ways:
        dw = densify(w)
        nsamp += len(dw)
        el = elevations(dw)
        gain += sum(max(0.0, el[i + 1] - el[i]) for i in range(len(el) - 1))
        loss += sum(max(0.0, el[i] - el[i + 1]) for i in range(len(el) - 1))
        los.append(min(el)); his.append(max(el))

    # On an out and back you climb the outward ascent and then climb the outward
    # descent on the way home, so the round trip total is gain + loss. It is not
    # gain doubled: a track that only ever goes up has no second climb in it.
    if shape == "Return":
        total_km = one_way_km * 2
        total_gain = gain + loss
    else:
        total_km = one_way_km
        total_gain = gain

    mins = total_km / 4 * 60 + total_gain / 10
    out[name] = dict(source=srclabel, shape=shape, ways=len(ways),
                     one_way_km=round(one_way_km, 2), km=round(total_km, 2),
                     gain=round(total_gain), one_way_gain=round(gain),
                     one_way_loss=round(loss), lo=round(min(los)), hi=round(max(his)),
                     naismith_min=round(mins), samples=nsamp, step_m=STEP_M, tags=tags)
    r = out[name]
    print(f"{name:24s} {srclabel:28s} {shape:16s} {r['km']:6.2f} km  "
          f"+{r['gain']:4d} m  {r['lo']:4d}-{r['hi']:4d} m  "
          f"{r['naismith_min']:4d} min  ({nsamp} samples)", flush=True)

json.dump(out, open("/tmp/fwh-walk-final2.json", "w"), indent=1)
print("\nwrote /tmp/fwh-walk-final2.json")
