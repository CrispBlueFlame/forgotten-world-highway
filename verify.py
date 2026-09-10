#!/usr/bin/env python3
"""Post-change verification. Every claim in the reply has to come from here."""
import json, re, math, os, subprocess, sys
from collections import Counter

# Resolve beside this script so the harness runs from a clone, not only Ross's tree.
# Set FWH_SRC to point it at a copy when mutation-testing.
SRC = os.environ.get("FWH_SRC") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "index.html")
src = open(SRC, encoding="utf-8").read()
fail = []

def check(ok, label, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {label}{('  ' + detail) if detail else ''}")
    if not ok:
        fail.append(label)

POIS = json.loads(re.search(r'const POIS = (\[.*?\]);\n', src, re.S).group(1))
TOWN = json.loads(re.search(r'const TOWN = (\[.*?\n\]);\n', src, re.S).group(1))
ALL = POIS + TOWN
cats = Counter(p["cat"] for p in POIS)
print(f"POIS {len(POIS)}  {dict(cats)}")
print(f"TOWN {len(TOWN)}  {dict(Counter(p['cat'] for p in TOWN))}\n")

# 1. the key must never be in the file.
# The key lives outside the tree and is not in the repo, so a clone cannot run the
# exact-match test. It is announced as SKIPPED rather than passing silently: a gate
# that cannot fail must never look like a gate that passed. The key-shaped sweep
# below runs everywhere and does not need the key.
KEYFILE = os.path.expanduser("~/.config/doc-api/key")
if os.path.exists(KEYFILE):
    key = open(KEYFILE).read().strip()
    check(key and key not in src, "DOC API key absent from index.html")
else:
    print(f"SKIP  DOC API key exact-match test (no key at {KEYFILE})")
check(not re.search(r"""x-api-key['"]?\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}"""
                    r"""|api[_-]?key['"]?\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}""", src),
      "no key-shaped literal in index.html")
check("api.doc.govt.nz" not in src or "x-api-key" not in src,
      "no live DOC API call in the page")

# 2. no em or en dashes
bad = [c for c in "—–" if c in src]
check(not bad, "no em/en dashes", f"found {bad}" if bad else "")

# 3. js parses
r = subprocess.run(["node", "--check", "/tmp/fwh-page.js"], capture_output=True, text=True) \
    if False else None
js = re.search(r'<script>\n(.*?)\n  </script>\s*</body>', src, re.S)
if not js:
    # fall back: last script block
    blocks = re.findall(r'<script>(.*?)</script>', src, re.S)
    body = blocks[-1]
else:
    body = js.group(1)
open("/tmp/fwh-check.js", "w").write(body)
r = subprocess.run(["node", "--check", "/tmp/fwh-check.js"], capture_output=True, text=True)
check(r.returncode == 0, "node --check on page script", r.stderr.strip()[:200])

# 4. the two requested options are present and complete
for want in ("Stratford Glockenspiel", "Taranaki Pioneer Village"):
    p = next((x for x in POIS if x["name"] == want), None)
    check(p is not None, f"{want} present")
    if p:
        check(bool(p.get("desc")) and p["cat"] == "attraction",
              f"{want} is an attraction with a description")
check(any(p["name"] == "Stratford Motel & Holiday Park" for p in POIS),
      "holiday park renamed to Ross's booking")
check(not any(p["name"] == "Stratford Holiday Park" for p in POIS),
      "old holiday park name gone")

# 5. Pioneer Village opening constraint is stated, since it is weekend only
pv = next((p for p in POIS if p["name"] == "Taranaki Pioneer Village"), None)
check(bool(pv and pv.get("warning")), "Pioneer Village carries its opening warning")

# 6. seasonal closures, verified at source, for a September trip window.
# Moki Track: DOC, "closed from 1 August to 31 October each year for the lambing
# season", no qualifier, so closed to everyone.
# Mount Damper Falls: DOC, "closed TO HUNTERS every year from 1 August to 31 October",
# so open to walkers. The page previously dropped "to hunters" and wrongly excluded it.
names = {p["name"] for p in POIS}
for shut in ("Moki Track", "Lauren's Lavender Farm", "Forgotten World Adventures depot"):
    check(shut not in names, f"seasonally shut stop removed: {shut}")
check("Mount Damper Falls" in names, "Mount Damper Falls kept (hunters-only closure)")
md = next((p for p in POIS if p["name"] == "Mount Damper Falls"), None)
check(bool(md and "hunters" in (md.get("warning") or "")),
      "Mount Damper Falls warning says hunters, not walkers")
check("Moki Track" not in src.split("const POIS")[1].split("];")[0],
      "no Moki Track entry left in POIS")
# The season block was removed at Ross's request. Its `.season b` rule is
# display:block + uppercase, written for one leading heading <b>, so the four inline
# <b> tags used for emphasis each rendered as their own red uppercase line.
check('<div class="season">' not in src, "season block removed")
check("lambing below" not in src, "no dangling reference to the removed season block")
# removing a stop is not enough: no other card may still promote a shut operator.
# The Whangamomona stop ended with "Forgotten World Adventures rail-cart tours also
# stop here" after the depot was removed.
for p in POIS:
    body = " ".join(str(p.get(f, "")) for f in ("desc", "warning", "access"))
    for shut in ("Forgotten World Adventures", "Lavender", "rail-cart", "rail cart"):
        check(shut not in body,
              f"no shut-operator reference in {p['name']}", f"mentions {shut!r}")

# 7. every DOC time is at least the Naismith estimate, or the DOC data is wrong way round
for p in POIS:
    d = (p.get("stats") or {}).get("doc")
    if d and d.get("mins"):
        check(d["mins"] >= p["stats"]["mins"] * 0.9,
              f"DOC time >= Naismith for {p['name']}",
              f"doc={d['mins']} naismith={p['stats']['mins']}")

# 8. return-trip climb is never more than gain+loss can allow
for p in POIS:
    s = p.get("stats")
    if s and s["shape"] == "Return":
        span = s["hi"] - s["lo"]
        check(s["gain"] >= span * 0.9 or s["gain"] == 0,
              f"return climb at least the altitude span for {p['name']}",
              f"gain={s['gain']} span={span}")

# 9. marker separation across every pair
def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    x = (math.sin((p2-p1)/2)**2
         + math.cos(p1)*math.cos(p2)*math.sin(math.radians(b[1]-a[1])/2)**2)
    return 2*R*math.asin(math.sqrt(x))
pairs = [(hav((a["lat"], a["lon"]), (b["lat"], b["lon"])), a["name"], b["name"])
         for i, a in enumerate(POIS) for b in POIS[i+1:]]
pairs.sort()
n = len(pairs)
print(f"\n{n} marker pairs, closest 5:")
for d, a, b in pairs[:5]:
    print(f"   {d:8.1f} m  {a}  <->  {b}")
check(pairs[0][0] > 1.0, "no two markers identical")
def mpp(z):
    return 156543.03392 * math.cos(math.radians(-39.1)) / (2**z)
# route stops open at zoom 15, where one pixel is about 3.7 m at this latitude
px = pairs[0][0] / mpp(15)
check(px >= 12, "closest route pair still separable at zoom 15", f"{px:.1f} px")

# 9b. town stops are packed tens of metres apart, so the page opens them at zoom 17
# instead. Same 12 px separability standard, measured at the zoom actually used, rather
# than a weakened threshold: a gate that cannot fail is worse than no gate.
check("p.where ? 17 : 15" in src, "town stops open at zoom 17")
tpairs = sorted((hav((a["lat"], a["lon"]), (b["lat"], b["lon"])), a["name"], b["name"])
                for i, a in enumerate(ALL) for b in ALL[i+1:])
print(f"\n{len(tpairs)} pairs including town, closest 4:")
for d, a, b in tpairs[:4]:
    print(f"   {d:8.1f} m  {d/mpp(17):5.1f} px@z17  {a}  <->  {b}")
check(tpairs[0][0] / mpp(17) >= 12, "closest pair including town separable at zoom 17",
      f"{tpairs[0][0]/mpp(17):.1f} px")
# town entries must never carry a km, or they would sort into the route and put 19
# ticks on the elevation ribbon at km 148.6
check(not any("km" in p for p in TOWN), "no town stop claims a highway km")
check(all(p.get("where") and p.get("desc") for p in TOWN), "every town stop has a where and a desc")
check(all(p["cat"] in ("food", "town") for p in TOWN), "town stops only use the two town categories")
# the ribbon is route-only on purpose
rib = src.split("const ticks =")[1].split(";")[0]
check("POIS.map" in rib, "elevation ribbon still plots POIS only, not ALL")

# 10. filter counts are derived, not typed.
# The old pattern here was r'class="fn">(\d+)<', which never matched because the real
# markup carries an id attribute between the class and the '>'. It passed vacuously
# while the markup held a stale 38 All / 8 Attractions against a live 40 / 10.
check("f === 'all' ? ALL.length" in src, "filter counts derived from ALL")
hard = re.findall(r'class="fn"[^>]*>\s*(\d+)\s*<', src)
check(not hard, "no hardcoded filter counts in markup", f"found {hard}" if hard else "")
# every filter button must name a category that exists, and every category must have a
# button, or a stop becomes unreachable from the list. The eat/drink content shipped
# once with no tab at all, which is exactly this failure.
btns = set(re.findall(r'data-filter="([a-z]+)"', src))
check(btns == {"all"} | {p["cat"] for p in ALL},
      "one filter button per category, no orphans",
      f"buttons={sorted(btns)} cats={sorted({p['cat'] for p in ALL})}")
labels = re.search(r'const CAT_LABEL = \{(.*?)\};', src, re.S).group(1)
for c in {p["cat"] for p in ALL}:
    check(f"{c}:" in labels, f"CAT_LABEL has a label for {c}")
    check(f".swatch.cat-{c}" in src and f".pin-{c}" in src, f"{c} has a swatch and a pin style")

# 11. stats integrity
for p in POIS:
    if p["cat"] == "walk":
        s = p.get("stats")
        check(bool(s), f"{p['name']} has stats")
        if s:
            for k in ("km", "gain", "lo", "hi", "mins", "shape"):
                check(k in s, f"{p['name']} stats has {k}")
            check(s["hi"] >= s["lo"], f"{p['name']} altitude range ordered")

# 12. superlatives in prose must be re-derivable, not asserted
# Two shipped false: Te Maire "longest proper walk close to the highway" and
# Ohinetonga "biggest single walk within reach of either end", both beaten by
# Taumarunui River Walk at 7.01km / 0.3km detour. A superlative is a count claim
# and nothing on the page re-derived it, so every one is listed here and checked.
SUPER = re.compile(r'\b(longest|biggest|largest|shortest|closest|highest|steepest|'
                   r'hardest|easiest|nearest|most|only)\b', re.I)
W = [p for p in POIS if p["cat"] == "walk"]
REVIEWED = {
    # sentence fragment -> callable returning (ok, detail), re-derived from POIS
    "longest detour of any walk here": lambda: (
        max(W, key=lambda p: p.get("detourKm", 0))["name"] == "Ohinetonga Track",
        f'max detour is {max(W, key=lambda p: p.get("detourKm", 0))["name"]} '
        f'at {max(p.get("detourKm", 0) for p in W)}km'),
    "costs no detour at all": lambda: (
        next(p for p in W if p["name"] == "Aukopae Tunnel walk").get("detourKm", 1) == 0,
        "Aukopae detourKm="
        f'{next(p for p in W if p["name"] == "Aukopae Tunnel walk").get("detourKm")}'),
}
# the three that shipped false, kept as named regressions
for _dead in ("longest proper walk close to the highway",
              "biggest single walk within reach",
              "easiest leg-stretch on the eastern half"):
    check(_dead not in src, f"retired false superlative absent: {_dead!r}")
found = []
for p in ALL:
    for field in ("desc", "warning"):
        t = p.get(field) or ""
        for sent in re.split(r'(?<=[.!?])\s+', t):
            if SUPER.search(sent):
                found.append((p["name"], field, sent.strip()))
print(f"\n{len(found)} superlative claim(s) in prose:")
for nm, field, sent in found:
    key = next((k for k in REVIEWED if k in sent), None)
    if key:
        ok, detail = REVIEWED[key]()
        check(ok, f"superlative re-derived: {nm}", detail)
    else:
        # not a walk-length claim; report so it is looked at, do not auto-fail
        print(f"   [prose] {nm} ({field}): {sent[:90]}")

print("\n" + ("ALL PASS" if not fail else f"{len(fail)} FAILURES: {fail}"))
sys.exit(1 if fail else 0)
