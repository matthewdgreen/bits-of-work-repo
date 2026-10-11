#!/usr/bin/env python3
"""Union OpenAlex / zbMATH / arXiv / DBLP pulls, dedupe against ePrint and each
other, keyword-screen the merged items, and write:

  data/candidates_phase1.jsonl   screened items NOT already covered by an ePrint
                                 candidate (those were labeled in Phase 0 or are
                                 in data/candidates_eprint_supp.jsonl)
  data/raw/openalex/seeds.jsonl  snowball seeds: ePrint include=yes items with a
                                 DOI or OpenAlex id found in the merged pool
  data/raw/dblp/enrich_dois.txt  DOIs of core-venue DBLP items lacking an
                                 abstract (for fetch_openalex.py dois)
  analysis/phase1_coverage.txt   coverage table

Dedup keys: DOI (lowercased), then normalized title (alnum, lowercase, first 60
chars). Year = earliest seen. Abstract = longest seen.

Usage: merge_sources.py [CLASS]. Without CLASS: the study's public-key classes,
ignoring symmetric hits, with the outputs above. CLASS=symmetric: symmetric
candidates only; ePrint coverage and snowball seeds come from
data/raw/symmetric/eprint_labeled_final.jsonl; outputs go to
data/raw/symmetric/candidates_merged.jsonl, data/raw/openalex/seeds_symmetric*.jsonl
and data/symmetric/coverage.txt.
"""
import json, glob, re, sys, collections, os, csv
def norm(t): return re.sub(r"[^a-z0-9]+", "", (t or "").lower())[:60]

ep = {json.loads(l)["eprint_id"]: json.loads(l) for l in open("data/eprint.jsonl")}
ONLY = sys.argv[1] if len(sys.argv) > 1 else None
assert ONLY in (None, "symmetric"), f"unknown class {ONLY}"
OUT_CAND, OUT_SEEDS, OUT_COV = (("data/raw/symmetric/candidates_merged.jsonl", "data/raw/openalex/seeds_symmetric", "data/symmetric/coverage.txt") if ONLY
                                else ("data/candidates_phase1.jsonl", "data/raw/openalex/seeds", "analysis/phase1_coverage.txt"))
EP_LABELS = "data/raw/symmetric/eprint_labeled_final.jsonl" if ONLY else "data/labeled_final.jsonl"
ep_cand = {json.loads(l)["eprint_id"] for l in open(EP_LABELS)}
if not ONLY and os.path.exists("data/candidates_eprint_supp.jsonl"):
    ep_cand |= {json.loads(l)["eprint_id"] for l in open("data/candidates_eprint_supp.jsonl")}
ep_titles = {}
for eid, r in ep.items(): ep_titles.setdefault(norm(r["title"]), eid)

# core venues whose papers we enrich with abstracts even when the title alone does not hit
CORE = re.compile(r"^(CRYPTO|FSE|Fast Software Encryption|EUROCRYPT|ASIACRYPT|PKC|Public Key Cryptography|TCC|CHES|PQCrypto|SAC|Selected Areas in Cryptography|ANTS|"
                  r"J\. Cryptol|Des\. Codes Cryptogr|Math\. Comput|LMS J\. Comput\. Math|Adv\. Math\. Commun|IACR Trans|IACR Commun|CT-RSA|"
                  r"INDOCRYPT|AFRICACRYPT|LATINCRYPT|ACISP|Math\. Cryptol|J\. Math\. Cryptol|Cryptogr\. Commun|WCC|IMACC|Algorithmic Number Theory)", re.I)

items, by_doi, by_title = {}, {}, {}
def add(rec, source):
    y = rec.get("year")
    rec["year"] = int(y) if str(y or "").strip()[:4].isdigit() else None
    t = norm(rec.get("title"))
    if len(t) < 10: return
    doi = (rec.get("doi") or "").lower().strip()
    k = by_doi.get(doi) if doi else None
    if k is None: k = by_title.get(t)
    if k is None:
        k = len(items); r = dict(rec); r["sources"] = set(); r["ids"] = {}; r["all_ids"] = set(); r["doi"] = doi; r["dois"] = set()
        r["eprint_match"] = ep_titles.get(t); items[k] = r
    r = items[k]
    r["sources"].add(source); r["ids"].setdefault(source.split("_")[0], rec["id"]); r["all_ids"].add(rec["id"])
    if doi: r["dois"].add(doi); by_doi[doi] = k; r["doi"] = r["doi"] or doi
    by_title.setdefault(t, k)
    if len(rec.get("abstract") or "") > len(r.get("abstract") or ""): r["abstract"] = rec["abstract"]
    if rec.get("year") and (not r.get("year") or rec["year"] < r["year"]): r["year"] = rec["year"]
    if not r.get("authors") and rec.get("authors"): r["authors"] = rec["authors"]
    if rec.get("venue") and not r.get("venue"): r["venue"] = rec["venue"]
    if rec.get("core_venue"): r["core_venue"] = True
    if rec.get("openalex_id"): r["openalex_id"] = rec["openalex_id"]

def jl(path):
    for l in open(path, encoding="utf-8"):
        try: yield json.loads(l)
        except json.JSONDecodeError: continue

src_counts = collections.Counter()
# DBLP first so its DOIs anchor the venue versions
if os.path.exists("data/raw/dblp/dblp_candidates.jsonl"):
    for w in jl("data/raw/dblp/dblp_candidates.jsonl"):
        if (w.get("venue") or "").startswith("IACR Cryptol. ePrint Arch"): continue  # ePrint itself; covered by data/eprint.jsonl
        src_counts["dblp"] += 1
        add({"id": "dblp:" + w["key"], "doi": w.get("doi", ""), "title": w["title"], "year": w.get("year"), "authors": w.get("authors", []),
             "venue": w.get("venue"), "abstract": "", "core_venue": bool(CORE.search(w.get("venue") or "")), "kind": w.get("kind")}, "dblp")
for p in sorted(glob.glob("data/raw/openalex/*.jsonl")):
    b = os.path.basename(p)
    if b.startswith("seeds"): continue
    src = ("openalex_phrase" if b.startswith("phrase_") else "openalex_doi" if b.startswith("doi_lookup") else "openalex_snowball")
    for w in jl(p):
        if w.get("type") in ("dataset", "peer-review", "editorial", "erratum", "paratext", "retraction"): continue
        src_counts[src] += 1
        add({"id": w["openalex_id"], "openalex_id": w["openalex_id"], "doi": w.get("doi", ""), "title": w["title"], "year": w.get("year"),
             "authors": w.get("authors", []), "venue": w.get("venue"), "abstract": w.get("abstract", "")}, src)
for p in sorted(glob.glob("data/raw/zbmath/*.jsonl")):
    for w in jl(p):
        src_counts["zbmath"] += 1
        add({"id": "zb:" + str(w.get("zbmath_id")), "doi": w.get("doi", ""), "title": w.get("title"), "year": w.get("year"),
             "authors": w.get("authors", []), "venue": w.get("venue"), "abstract": w.get("abstract", "")}, "zbmath")
for p in sorted(glob.glob("data/raw/arxiv/*.jsonl")):
    for w in jl(p):
        src_counts["arxiv"] += 1
        add({"id": "arXiv:" + w["arxiv_id"], "doi": w.get("doi", ""), "title": w["title"], "year": w.get("year"),
             "authors": w.get("authors", []), "venue": w.get("journal_ref") or "arXiv", "abstract": w.get("abstract", "")}, "arxiv")

src = open("pipeline/candidates.py").read().split("counts = collections.Counter()")[0]
ns = {}; exec(src, ns); PC = ns["PC"]; EXCL = ns["EXCL"]

# Tiering (Phase 1 only; ePrint Phase 0 was screened untiered). Tier A is classified first,
# tier B only if budget remains. Calibrated on Phase 0 per-signature inclusion yields
# (analysis/phase1_tiering.txt): weak labels are generic words that also occur outside
# cryptanalysis; LOWYIELD sole signatures had <=3% inclusion on ePrint.
WEAK = {"code:qc schemes", "code:sd", "code:rank metric", "code:lpn", "code:quantum isd", "code:code-based crypto attack", "code:structural",
        "lattice:reduction", "lattice:svp/cvp", "lattice:pqc lattice scheme", "lattice:quantum lattice", "lattice:ntru", "lattice:lwe family",
        "lattice:cryptanalysis+lattice", "lattice:lattice+cryptanalysis", "comparator:multivariate", "comparator:factoring/nfs",
        "comparator:isogeny wide", "comparator:ffdlp records", "ecdlp:named curve", "ecdlp:koblitz", "ecdlp:dlog generic", "ecdlp:bsgs",
        "ecdlp:dlog+curve", "ecdlp:quantum ecc", "ecdlp:record-ish"}
LOWYIELD = {("lattice:pqc lattice scheme",), ("ecdlp:named curve",), ("code:qc schemes",), ("lattice:quantum lattice",), ("ecdlp:koblitz",),
            ("code:code-based crypto attack",), ("lattice:pqc lattice scheme", "lattice:quantum lattice"),
            ("lattice:ntru", "lattice:pqc lattice scheme"), ("lattice:lwe family", "lattice:pqc lattice scheme")}
CTX = re.compile(r"crypt|attack|secur|cipher|\bkeys?\b|signature|\bkem\b|post[- ]quantum|discrete log|factor", re.I)
def tier(hits, text, sources):
    labs = tuple(sorted(f"{c}:{x}" for c, v in hits.items() for x in v))
    if any(l not in WEAK for l in labs): return "A"
    if labs in LOWYIELD: return "B"
    if CTX.search(text) or any("snowball" in s for s in sources): return "A"
    return "B"

new, cov, cov_cls = [], collections.Counter(), collections.defaultdict(collections.Counter)
enrich = set()
for k, r in items.items():
    if r.get("core_venue") and not r.get("abstract") and r.get("doi") and not r.get("eprint_match"): enrich.add(r["doi"])
    text = (r["title"] or "") + " \n " + (r.get("abstract") or "")
    hits = {c: [lab for rx, lab in pats if rx.search(text)] for c, pats in PC.items()}
    hits = {c: v for c, v in hits.items() if v}
    if hits.get("ecdlp") == ["dlog generic"] and set(hits) <= {"ecdlp", "symmetric"}: del hits["ecdlp"]
    if ONLY:
        if ONLY not in hits: continue
    else: hits.pop("symmetric", None)
    if not hits: continue
    srcs = "|".join(sorted(s.split("_")[0] for s in r["sources"]))
    for c in hits: cov_cls[c][srcs] += 1
    if r["eprint_match"] in ep_cand: cov["covered_by_eprint_candidate"] += 1; continue
    cov["new"] += 1
    ids = r["ids"]
    rid = ids.get("dblp") or ids.get("openalex") or ids.get("arxiv") or ids.get("zbmath")
    new.append({"id": rid, "title": r["title"], "authors": r.get("authors", []), "author_count": len(r.get("authors", [])),
                "year": r.get("year"), "venue": r.get("venue") or "", "doi": r.get("doi", ""), "abstract": r.get("abstract") or "",
                "sources": sorted(r["sources"]), "other_ids": ids, "all_ids": sorted(r["all_ids"]), "eprint_match": r["eprint_match"], "kw_hits": hits,
                "excl_hints": sorted(set(m.group(0).lower() for m in EXCL.finditer(text))),
                "tier": tier(hits, text + " " + (r.get("venue") or ""), r["sources"])})
# ePrint items newly screened in by widened patterns (rubric v0.3 / candidates.py isogeny-wide) join the Phase 1 pool
if not ONLY and os.path.exists("data/candidates_eprint_supp.jsonl"):
    for r in jl("data/candidates_eprint_supp.jsonl"):
        r = dict(r); r["id"] = r.pop("eprint_id"); r["sources"] = ["eprint_supp"]; r["tier"] = "A"; r["venue"] = "IACR ePrint (" + (r.pop("category", "") or "") + ")"
        new.append(r); cov["eprint_supp"] += 1
new.sort(key=lambda r: (r.get("year") or 0, r["title"]))
with open(OUT_CAND, "w") as f:
    for r in new: f.write(json.dumps(r, ensure_ascii=False) + "\n")
open("data/raw/dblp/enrich_dois.txt", "w").write("\n".join(sorted(enrich)) + "\n")

# snowball seeds: ePrint include=yes items mapped to a DOI / OpenAlex id via title
seeds = []; unresolved = []
title_to_k = {norm(r["title"]): k for k, r in items.items()}
def ep_included():
    if not ONLY: return [row for row in csv.DictReader(open("data/export/eprint_included.csv")) if row["include"] == "yes"]
    rows = [json.loads(l) for l in open(EP_LABELS)]
    return [{"eprint_id": r["eprint_id"], "title": r["title"]} for r in rows if r["label"]["include"] == "yes" and ONLY in r["label"]["problem_tags"]]
for row in ep_included():
    k = title_to_k.get(norm(row["title"]))
    r = items.get(k) if k is not None else None
    if r and (r.get("doi") or r.get("openalex_id")):
        seeds.append({"seed_id": row["eprint_id"], "doi": r.get("doi", ""), "openalex_id": r.get("openalex_id", ""), "title": row["title"]})
    else: unresolved.append({"seed_id": row["eprint_id"], "title": row["title"]})
os.makedirs("data/raw/openalex", exist_ok=True)
with open(OUT_SEEDS + ".jsonl", "w") as f:
    for s in seeds: f.write(json.dumps(s, ensure_ascii=False) + "\n")
with open(OUT_SEEDS + "_unresolved.jsonl", "w") as f:
    for s in unresolved: f.write(json.dumps(s, ensure_ascii=False) + "\n")

yb = collections.Counter(("pre-2006" if (r.get('year') or 0) < 2006 else "2006-2016" if (r.get('year') or 0) <= 2016 else "2017+") for r in new)
lines = [f"raw rows by source: {dict(src_counts)}",
         f"merged items: {len(items)}; keyword-screened: {cov['covered_by_eprint_candidate'] + cov['new']}; covered by ePrint candidates: {cov['covered_by_eprint_candidate']}; NEW candidates: {cov['new']}",
         f"new candidates by era: {dict(yb)}",
         f"new candidates with abstract: {sum(1 for r in new if r['abstract'])} / {len(new)}",
         f"new candidates by tier: {dict(collections.Counter(r['tier'] for r in new))}; tier A with abstract: {sum(1 for r in new if r['tier']=='A' and r.get('abstract'))}",
         f"new candidates by class: {dict(collections.Counter(c for r in new for c in r['kw_hits']))}",
         f"core-venue items lacking abstract (enrich_dois.txt): {len(enrich)}",
         f"snowball seeds resolved: {len(seeds)}; unresolved: {len(unresolved)}",
         "screened items by source combination, per class:"]
for c, cnt in cov_cls.items(): lines.append(f"  {c}: {dict(cnt.most_common(10))}")
open(OUT_COV, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
