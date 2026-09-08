#!/usr/bin/env python3
"""Remove stops that are shut for the September trip window, verified at source.

Trip window: Thu 10 Sep to Mon 14 Sep 2026.

REMOVED, each confirmed from the operator or DOC, not from prior session notes:
  Moki Track        doc.govt.nz: "The track is closed from 1 August to 31 October
                    each year for the lambing season." Closed to everyone. This was
                    NOT on the page: the stop shipped as an available full-day walk.
  Lauren's Lavender laurenslavender.co.nz: "We are open from the end of October,
                    through to late April." Page had said "October to mid-May",
                    wrong at both ends.
  Forgotten World   forgottenworldadventures.co.nz: "We are now closed for the winter
  Adventures        months"; "Our 2026/27 season runs from 10th October 2026 to
                    15th May 2027."

KEPT, and the page corrected:
  Mount Damper      doc.govt.nz: "The track is closed TO HUNTERS every year from
  Falls             1 August to 31 October for the lambing season." Open to walkers.
                    The page had dropped "to hunters" and called it shut, so it was
                    wrongly excluding the North Island's second-highest waterfall.
                    Same sentence position on both DOC pages; Moki's lacks the
                    qualifier and this one has it.

Consequential fixes: the DOC-managed track count in the drawer is re-derived rather
than carried, the season block is rewritten, and the static filter-count fallbacks in
the markup are emptied so they cannot go stale again (they read 38/8 while the live
page rendered 40/10).
"""
import json, re, shutil, datetime

SRC = "index.html"
src = open(SRC, encoding="utf-8").read()
m = re.search(r'const POIS = (\[.*?\]);\n', src, re.S)
POIS = json.loads(m.group(1))
before = len(POIS)

REMOVE = ["Moki Track", "Lauren's Lavender Farm", "Forgotten World Adventures depot"]
for n in REMOVE:
    assert any(p["name"] == n for p in POIS), f"not present: {n}"
POIS = [p for p in POIS if p["name"] not in REMOVE]
for n in REMOVE:
    print(f"removed  {n}")

# Mount Damper Falls stays, with the misreading corrected
OLD_W = ("Closed every year from 1 August to 31 October for lambing. Reopens "
         "1 November, so check before committing to the gravel.")
NEW_W = ("DOC closes this track to hunters from 1 August to 31 October for lambing, "
         "but it stays open to walkers, so it is on for these dates. Still 21km of "
         "mostly gravel each way, so commit to the drive before you set off.")
hit = 0
for p in POIS:
    if p["name"] == "Mount Damper Falls":
        assert p.get("warning") == OLD_W, repr(p.get("warning"))
        p["warning"] = NEW_W
        hit += 1
assert hit == 1
print("corrected Mount Damper Falls: closed to hunters only, open to walkers")

new = json.dumps(POIS, ensure_ascii=False, separators=(",", ":"))
out = src[:m.start(1)] + new + src[m.end(1):]

# DOC-managed track count in the drawer, re-derived not carried
ndoc = sum(1 for p in POIS if (p.get("stats") or {}).get("doc"))
old_c = "For the four\n      tracks DOC manages that line is DOC's"
assert old_c in out
WORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
out = out.replace(old_c, f"For the {WORD[ndoc]}\n      tracks DOC manages that line is DOC's")
print(f"DOC-managed track count re-derived: 4 -> {ndoc}")

# the Moki example is still the clearest one, but it is no longer a listed stop
old_e = ("OpenStreetMap maps only the formed middle of the Moki Track, while DOC's line\n"
         "      includes the 3km of farmland at each end, which is the difference between 11.8km and\n"
         "      18km.")
assert old_e in out
out = out.replace(old_e,
    ("on the Moki Track, taken off the list for lambing below, OpenStreetMap maps only\n"
     "      the formed middle while DOC's line includes the 3km of farmland at each end, which is\n"
     "      the difference between 11.8km and 18km."))
print("reworded the Moki example so it does not imply a listed stop")

# season block
old_s = re.search(r'<div class="season">.*?</div>', out, re.S).group(0)
new_s = ('<div class="season">\n'
         '        <b>Taken off the list for September</b>\n'
         '        Three stops are shut for these dates and have been removed:\n'
         '        <b>Moki Track</b>, which DOC closes from 1 August to 31 October for lambing and\n'
         '        reopens 1 November; <b>Lauren\'s Lavender Farm</b>, open end of October to late\n'
         '        April; and <b>Forgotten World Adventures</b>, whose 2026/27 rail cart season runs\n'
         '        10 October 2026 to 15 May 2027.\n'
         '        <b>Mount Damper Falls stays in.</b> DOC closes that one to hunters only over\n'
         '        lambing, not to walkers, so the waterfall is open. Everything else on this page is\n'
         '        open year round, weather allowing.\n'
         '      </div>')
out = out.replace(old_s, new_s)
print("rewrote the season block")

# static filter-count fallbacks: emptied so they cannot go stale
stale = re.findall(r'(<span class="fn" id="c\w+">)(\d+)(</span>)', out)
out = re.sub(r'(<span class="fn" id="c\w+">)\d+(</span>)', r'\1\2', out)
print(f"emptied {len(stale)} static filter-count fallbacks (were {[s[1] for s in stale]})")

assert not [c for c in "—–" if c in out], "dash characters present"
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(SRC, f"/tmp/fwh-index-backup-{stamp}.html")
open(SRC, "w", encoding="utf-8").write(out)

from collections import Counter
print(f"\nbackup /tmp/fwh-index-backup-{stamp}.html")
print(f"POIS {before} -> {len(POIS)}   {dict(Counter(p['cat'] for p in POIS))}")

# --- second pass: dangling references to removed operators -------------------
# Rendering the cards showed the Whangamomona stop still ending with "Forgotten World
# Adventures rail-cart tours also stop here", promoting a service that does not run
# until 10 October. Removing a stop is not enough; the other cards' prose has to be
# swept for references to it.
src = open(SRC, encoding="utf-8").read()
m = re.search(r'const POIS = (\[.*?\]);\n', src, re.S)
POIS = json.loads(m.group(1))
DANGLE = " Forgotten World Adventures rail-cart tours also stop here."
n = 0
for p in POIS:
    if p.get("desc", "").endswith(DANGLE):
        p["desc"] = p["desc"][:-len(DANGLE)]
        print(f"trimmed dangling rail-cart line from {p['name']}")
        n += 1
assert n == 1, n
new = json.dumps(POIS, ensure_ascii=False, separators=(",", ":"))
out = src[:m.start(1)] + new + src[m.end(1):]
assert not [c for c in "—–" if c in out]
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
shutil.copy2(SRC, f"/tmp/fwh-index-backup-{stamp}.html")
open(SRC, "w", encoding="utf-8").write(out)
print(f"backup /tmp/fwh-index-backup-{stamp}.html")
