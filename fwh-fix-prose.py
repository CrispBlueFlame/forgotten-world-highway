#!/usr/bin/env python3
"""Four prose/provenance defects found by rendering the page and re-deriving its claims.

1. Moki desc said "treat it as an out and back". Written when the page thought the
   track was 11.8km. At DOC's 18km one way, Advanced, 8hr, an out and back is 36km
   and about 16 hours. The advice is now unsafe, not just stale.

2. Te Maire desc: "The longest proper walk close to the highway". False. Taumarunui
   River Walk is 7.01km at a 0.3km detour: both longer and closer. Te Maire is 3.62km.
   Also false before this session (3.58 vs 7.02), so pre-existing.

3. Ohinetonga desc: "the biggest single walk within reach of either end". False.
   Taumarunui River Walk 7.01km and Tatu 8.43km both beat its 4.21km, and Ohinetonga
   has the largest detour of any walk on the page at 28.4km. Also pre-existing.

4. Moki and Mount Damper Falls carried an OSM `surface` tag, but both are now measured
   from DOC geometry. The patch only overwrites surface when the new run supplies one,
   and the DOC path never populates tags, so those two values are orphaned from a source
   the page no longer uses. Moki's in particular came from the 11.8km bush section, the
   very geometry proven to be only part of the track. Dropped; the two OSM-sourced walks
   keep theirs because the tag and the measurement came from the same ways.
"""
import json, re, shutil, datetime

SRC = "/home/ross/Documents/Claude/Projects/Forgotten World Highway/index.html"
src = open(SRC, encoding="utf-8").read()
m = re.search(r'const POIS = (\[.*?\]);\n', src, re.S)
POIS = json.loads(m.group(1))

DESC = {
 "Moki Track":
  ("A long backcountry track running north off Moki Road, through the same bush the "
   "tunnel was cut for. Unformed in places, with no loop back, so the only sane way to "
   "use it is to walk in as far as suits and turn around on your own clock. The drive "
   "in is gravel."),
 "Te Maire Loop Track":
  ("A loop track in the Whanganui River country off River Road, walkers only and no "
   "bikes. Only a couple of kilometres off the highway, and a genuine change of pace "
   "from the driving."),
 "Ohinetonga Track":
  ("A genuine loop through the Ohinetonga Scenic Reserve at Owhango, in tall podocarp "
   "forest above the Whakapapa River. Unlike most of the tracks out here the road in is "
   "sealed the whole way, but it is a 28km run off the highway, the longest detour of "
   "any walk here, so it suits a night spent at the Taumarunui end."),
}
for p in POIS:
    if p["name"] in DESC:
        assert p["desc"] != DESC[p["name"]], p["name"]
        p["desc"] = DESC[p["name"]]
        print(f"rewrote desc: {p['name']}")
    if p["name"] in ("Moki Track", "Mount Damper Falls"):
        s = p.get("stats") or {}
        if "surface" in s:
            print(f"dropped orphaned surface {s['surface']!r} from {p['name']} "
                  f"(now sourced {s.get('osm')})")
            del s["surface"]

new = json.dumps(POIS, ensure_ascii=False, separators=(",", ":"))
out = src[:m.start(1)] + new + src[m.end(1):]
bad = [c for c in "—–" if c in out]
assert not bad, f"dash characters present: {bad}"
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(SRC, f"/tmp/fwh-index-backup-{stamp}.html")
open(SRC, "w", encoding="utf-8").write(out)
print(f"\nbackup /tmp/fwh-index-backup-{stamp}.html")
