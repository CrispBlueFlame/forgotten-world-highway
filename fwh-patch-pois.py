#!/usr/bin/env python3
"""Patch POIS in place: add the two Stratford-end options Ross asked for, correct
the holiday park's name and detail, and fold DOC's official figures into the walks.

Coordinates are OSM/Nominatim verified, detours are OSRM drive distance and time,
and walk figures come from fwh-walk-final2.json. Nothing here is estimated.
"""
import json, re, shutil, datetime

SRC = "/home/ross/Documents/Claude/Projects/Forgotten World Highway/index.html"
src = open(SRC, encoding="utf-8").read()
m = re.search(r'const POIS = (\[.*?\]);\n', src, re.S)
POIS = json.loads(m.group(1))
before = len(POIS)

walk = json.load(open("/tmp/fwh-walk-final2.json"))
docmeta = json.load(open("/tmp/fwh-doc-meta.json"))

# ---------------------------------------------------------------- new options
GLOCK = {
    "name": "Stratford Glockenspiel",
    "cat": "attraction",
    "lat": -39.3395255, "lon": 174.2849504,
    "km": 0.0, "detourKm": 0.2, "detourMin": 1,
    "desc": ("New Zealand's only glockenspiel, on the clock tower in the middle of "
             "Broadway. Four times a day the doors open and carved figures play out "
             "the balcony scene from Romeo and Juliet, three Romeos and three Juliets "
             "in turn, ending hand in hand. It runs about five minutes and the tower "
             "is a two minute walk from the main street parking, so it costs you "
             "nothing but the wait for the next one."),
    "access": "10am, 1pm, 3pm, 7pm daily",
}
PIONEER = {
    "name": "Taranaki Pioneer Village",
    "cat": "attraction",
    "lat": -39.3565027, "lon": 174.2930827,
    "km": 0.0, "detourKm": 2.3, "detourMin": 3,
    "desc": ("A ten acre outdoor museum just south of Stratford with about 40 "
             "relocated buildings dating from roughly 1850 to 1950, including a "
             "church, a courthouse and a railway station. The Pioneer Express runs a "
             "loop of the grounds at 11am, 1pm and 3pm, and the Shakee Pear cafe and "
             "playground are on site. Budget a couple of hours if you go in."),
    "warning": ("Weekends and public holidays only, 10am to 4pm, unless it is school "
                "holidays when it opens seven days. Saturday or Sunday is the only "
                "way this one works on a Thursday to Monday trip."),
}

names = {p["name"] for p in POIS}
for poi in (GLOCK, PIONEER):
    if poi["name"] in names:
        POIS = [p for p in POIS if p["name"] != poi["name"]]
    POIS.append(poi)
    print(f"added {poi['name']}")

# ------------------------------------------------- holiday park, named and detailed
for p in POIS:
    if p["name"] == "Stratford Holiday Park":
        p["name"] = "Stratford Motel & Holiday Park"
        p["desc"] = ("Powered and unpowered sites on Page Street, plus cabins, kitchen "
                     "cabins, tourist flats, motel units and a backpacker lodge. On site "
                     "there is a heated swimming pool, a spa, a camp kitchen, laundry, "
                     "BBQ, a TV room and a playground, and there is a dump station by the "
                     "toilet block in the middle of the park. A signposted bush walk "
                     "leaves the bottom of the park and reaches town in about 15 minutes, "
                     "so the van can stay put for the evening.")
        p["access"] = "dump station on site"
        print("renamed and expanded Stratford Motel & Holiday Park")

# The glockenspiel has its own card now, so the town waypoint keeps the practical
# job of being the last fuel, water and supermarket before Taumarunui.
for p in POIS:
    if p["name"] == "Stratford" and p["cat"] == "waypoint":
        p["desc"] = ("Western end of the Forgotten World Highway, and the last fuel, "
                     "water and supermarket before Taumarunui 148km away. Z and Caltex "
                     "sit on Broadway and Allied on Regan Street runs 24 hours. Fill up "
                     "here: there is no fuel at all between the two ends.")
        print("trimmed Stratford waypoint to its practical role")

# ------------------------------------------------------------- walk figures
for p in POIS:
    if p["cat"] != "walk":
        continue
    w = walk.get(p["name"])
    if not w:
        print(f"  !! no rebuilt metrics for {p['name']}")
        continue
    s = p["stats"]
    old = dict(s)
    s["km"] = w["km"]
    s["gain"] = w["gain"]
    s["lo"] = w["lo"]
    s["hi"] = w["hi"]
    s["mins"] = w["naismith_min"]
    s["shape"] = w["shape"]
    s["osm"] = w["source"]
    if w.get("tags", {}).get("surface"):
        s["surface"] = w["tags"]["surface"]
    d = docmeta.get(p["name"])
    if d:
        s["doc"] = {k: v for k, v in d.items() if v is not None}
    ch = [k for k in ("km", "gain", "mins", "lo", "hi") if old.get(k) != s.get(k)]
    print(f"  {p['name']:24s} {'changed: ' + ','.join(ch) if ch else 'unchanged'}"
          f"   {old.get('km')}->{s['km']}km  {old.get('mins')}->{s['mins']}min"
          + (f"  DOC {d['time']} {d['grade']}" if d else ""))

# Moki is the one that materially changes character: 18km one way on an
# Advanced-graded track is a full day, not the afternoon the old figures implied.
for p in POIS:
    if p["name"] == "Moki Track":
        p["warning"] = ("DOC grades this Advanced and gives it 8 hours for the 18km, "
                        "one way, with no loop back. It is a full day out and the road "
                        "in is gravel, so it is a turn-around-on-your-own-clock walk "
                        "rather than something to finish.")
        print("added Moki Track warning")

POIS.sort(key=lambda p: (p["km"], p["name"]))
new = json.dumps(POIS, ensure_ascii=False, separators=(",", ":"))
out = src[:m.start(1)] + new + src[m.end(1):]

bad = [c for c in "—–" if c in out]
assert not bad, f"dash characters present: {bad}"

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(SRC, f"/tmp/fwh-index-backup-{stamp}.html")
open(SRC, "w", encoding="utf-8").write(out)

from collections import Counter
c = Counter(p["cat"] for p in POIS)
print(f"\nbackup /tmp/fwh-index-backup-{stamp}.html")
print(f"POIS {before} -> {len(POIS)}   {dict(c)}")
print(f"with stats: {sum(1 for p in POIS if p.get('stats'))}, "
      f"with doc: {sum(1 for p in POIS if p.get('stats',{}).get('doc'))}, "
      f"with warning: {sum(1 for p in POIS if p.get('warning'))}")
