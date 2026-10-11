#!/usr/bin/env python3
"""Combined counts: Phase 0 (ePrint) + Phase 1 (DBLP/OpenAlex/zbMATH/arXiv) labels.

Usage: phase1_counts.py [--borderline] > analysis/phase1_counts.txt
Inputs: data/labeled_final.jsonl (Phase 0), data/phase1/labeled_final.jsonl (Phase 1).
Phase 1 candidates were deduped against ePrint candidates before labeling, so the
two sets are disjoint by construction.

Views:
  all        every included item
  vetted     ePrint + items indexed by DBLP (drops OpenAlex/zbMATH/arXiv-only items,
             which is where predatory/unreviewed venues concentrate)
Attribution: fractional (pipeline/attribution.json) and touch; plus "all lattices"
(union of MLWE_structured and LWE_plain), the recommended headline (phase0_report §4.2).
"""
import json, sys, collections, os
sys.path.insert(0, "pipeline")
from symmetric_labels import join  # the symmetric extension's labels (notes/symmetric_extension.md)
EXCL = set(json.load(open('data/manual_exclusions.json'))['items'])
BORDER = "--borderline" in sys.argv
POL = json.load(open("pipeline/attribution.json"))
# version weights: preprints/duplicates of a counted work 0, journal extensions 1/3
# (pipeline/build_version_weights.py); ids not listed count 1
VW = {}
if os.path.exists("data/dedup/version_weights.csv"):
    import csv
    VW = {r["id"]: float(r["weight"]) for r in csv.DictReader(open("data/dedup/version_weights.csv"))}
CLASSES = POL["classes"]; FRAC = POL["fractional"]; EFF = set(POL["effort_categories"])
LAT = {"MLWE_structured", "LWE_plain"}

def rows():
    for l in open("data/labeled_final.jsonl"):
        r = json.loads(l); r["_src"] = "eprint"; r["_vetted"] = True; r["_id"] = r["eprint_id"]; yield r
    p = "data/phase1/labeled_final.jsonl"
    if os.path.exists(p):
        for l in open(p):
            r = json.loads(l)
            srcs = r.get("sources", [])
            r["_src"] = "eprint" if srcs == ["eprint_supp"] else "phase1"
            r["_vetted"] = r["_src"] == "eprint" or any(s == "dblp" for s in srcs)
            r["_id"] = r["id"]
            if r["_id"] not in EXCL: yield r
    # round 2: v2-screen items + 10% random sample of tier B (data/phase1/round2/)
    p = "data/phase1/round2/labeled_final.jsonl"
    if os.path.exists(p):
        tb = {json.loads(l)["id"] for l in open("data/phase1/round2/pool_tierB_sample.jsonl")}
        for l in open(p):
            r = json.loads(l); srcs = r.get("sources", [])
            r["_src"] = "eprint" if srcs == ["eprint"] else "phase1"
            r["_vetted"] = r["_src"] == "eprint" or "dblp" in srcs
            r["_id"] = r["id"]; r["_tierB"] = r["id"] in tb
            if r["_id"] not in EXCL: yield r

TB_W = 8353 / 835  # tier-B population / sample size, for the extrapolated view
def yr(r):
    y = str(r.get("year") or "")[:4]
    return int(y) if y.isdigit() else 0
def era(y): return "pre-2006" if (y or 0) < 2006 else ("2006-2016" if y <= 2016 else "2017-2026")
def ok(r): return r["label"].get("include") == "yes" or (BORDER and r["label"].get("include") == "borderline")

def table(sel, title, tb_weight=1.0):
    frac = collections.defaultdict(float); touch = collections.Counter(); fe = collections.defaultdict(float)
    cats = collections.defaultdict(collections.Counter); auth = collections.defaultdict(set); lat_touch = 0; lat_auth = set()
    n = 0
    for r in sel:
        L = r["label"]
        if not ok(r) or L.get("category") not in EFF: continue
        vw = VW.get(r["_id"], 1.0)
        if vw == 0: continue
        n += 1; W = (tb_weight if r.get("_tierB") else 1.0) * vw
        tags = L.get("problem_tags") or {}; tot = sum(tags.values()) or 1.0; touched = set()
        for t, w in tags.items():
            for c, cw in FRAC.get(t, {}).items():
                frac[c] += W * w / tot * cw; fe[(c, era(yr(r)))] += W * w / tot * cw; touched.add(c)
        for c in touched:
            touch[c] += W; cats[c][L["category"]] += 1; auth[c].update(r.get("authors") or [])
        if touched & LAT: lat_touch += W; lat_auth.update(r.get("authors") or [])
    out = [f"== {title}: {n} effort items (A-F,H); borderline counted: {BORDER}",
           f"{'class':18s} {'frac':>8s} {'touch':>6s} {'authors':>8s} {'pre2006':>8s} {'06-16':>8s} {'17-26':>8s}  categories"]
    for c in CLASSES:
        cs = " ".join(f"{k}:{v}" for k, v in sorted(cats[c].items()))
        out.append(f"{c:18s} {frac[c]:8.1f} {touch[c]:6.0f} {len(auth[c]):8d} {fe[(c,'pre-2006')]:8.1f} {fe[(c,'2006-2016')]:8.1f} {fe[(c,'2017-2026')]:8.1f}  {cs}")
    lf = frac["MLWE_structured"] + frac["LWE_plain"]
    out.append(f"{'ALL LATTICES':18s} {lf:8.1f} {lat_touch:6.0f} {len(lat_auth):8d} "
               + " ".join(f"{fe[('MLWE_structured',e)] + fe[('LWE_plain',e)]:8.1f}" for e in ("pre-2006", "2006-2016", "2017-2026")))
    return "\n".join(out) + "\n"

def with_symmetric(rows):
    rows = list(rows); retagged, extra = join({r["_id"]: r for r in rows})
    for r in extra:
        srcs = r.get("sources", [])
        r["_src"] = "eprint" if r["round"] == "eprint" else "phase1"
        r["_vetted"] = r["_src"] == "eprint" or "dblp" in srcs or "eprint" in srcs
        r["_id"] = r["id"]
    return [retagged[r["_id"]] for r in rows] + extra

R = with_symmetric(rows())
print(f"labeled rows: {len(R)} (ePrint {sum(r['_src']=='eprint' for r in R)}, Phase 1 {sum(r['_src']=='phase1' for r in R)})\n")
print(table([r for r in R if r["_src"] == "eprint"], "ePrint only (Phase 0 + isogeny supplement)"))
print(table([r for r in R if r["_src"] == "phase1"], "Phase 1 new items only"))
print(table(R, "COMBINED, all sources"))
print(table([r for r in R if r["_vetted"]], "COMBINED, vetted (ePrint + DBLP-indexed)"))
print(table([r for r in R if (r["label"].get("confidence") or 0) >= 0.6], "COMBINED, all sources, classifier confidence >= 0.6"))
print(table([r for r in R if r["_vetted"] and (r["label"].get("confidence") or 0) >= 0.6], "COMBINED, vetted, confidence >= 0.6 (most conservative)"))
print(table(R, f"COMBINED + tier-B extrapolation (sample items weighted x{TB_W:.2f}; author counts not extrapolated)", tb_weight=TB_W))
print(table([r for r in R if r["_vetted"]], f"COMBINED vetted + tier-B extrapolation (x{TB_W:.2f})", tb_weight=TB_W))

# category E / records and H lists from Phase 1 for cross-checking the records track
print("Phase 1 items labeled E or is_record:")
for r in sorted(R, key=yr):
    L = r["label"]
    if r["_src"] == "phase1" and ok(r) and (L.get("category") == "E" or L.get("is_record")):
        print(f"  {str(r.get('year')):5s} {','.join(L.get('problem_tags', {}))[:24]:24s} {r['title'][:90]}")
