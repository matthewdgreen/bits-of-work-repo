#!/usr/bin/env python3
"""Author map, step 2: career-stage evidence for persons with >= 1 included item.

Subcommands (each caches raw responses under data/raw/enrich/ and resumes):
  wikidata  SPARQL by DBLP author id (P2456): Wikidata QID, Math Genealogy id
            (P549), birth date (P569), ORCID (P496). Batches of 150 ids.
  orcid     ORCID public API v3.0 /activities for every known ORCID (DBLP person
            record, DBLP author attribute, or Wikidata): education and
            employment entries with role titles and dates.
  mgp       Math Genealogy Project pages for every known MGP id (DBLP person
            record or Wikidata): PhD year, institution, thesis title.
            Honors the site's robots.txt crawl delay (10 s).

Usage: python3 -I pipeline/authors_enrich.py wikidata|orcid|mgp
Input: data/authors/authors.csv (analysis/author_map.py).
"""
import csv, json, os, re, sys, time, html, urllib.request, urllib.parse, urllib.error

UA = {"User-Agent": "bits-of-work-symmetric-extension/0.1 (John Servil; mailto:johnservil@proton.me; https://github.com/johnservil)"}
RAW = "data/raw/enrich"
WD_OUT = f"{RAW}/wikidata.jsonl"
ORCID_DIR = f"{RAW}/orcid"
MGP_DIR = f"{RAW}/mgp"


def persons():
    return [r for r in csv.DictReader(open("data/authors/authors.csv")) if int(r["n_items_yes"]) > 0]


def get(url, accept=None, tries=6, delay=1.0):
    h = dict(UA)
    if accept: h["Accept"] = accept
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410): return None
            time.sleep(min(120, delay * 4 ** i)); print("retry", i, e.code, url[:80], flush=True)
        except Exception as e:
            time.sleep(min(120, delay * 4 ** i)); print("retry", i, type(e).__name__, url[:80], flush=True)
    return None


def wd_rows():
    if not os.path.exists(WD_OUT): return {}
    return {d["dblp_pid"]: d for d in map(json.loads, open(WD_OUT))}


def cmd_wikidata():
    os.makedirs(RAW, exist_ok=True)
    done = wd_rows(); done_pids = set(done) | {l.strip() for l in open(WD_OUT + ".queried")} if os.path.exists(WD_OUT + ".queried") else set(done)
    pids = sorted({r["dblp_pid"] for r in persons() if r["dblp_pid"]} - done_pids)
    print(f"{len(pids)} DBLP pids to query")
    with open(WD_OUT, "a") as out, open(WD_OUT + ".queried", "a") as q:
        for i in range(0, len(pids), 150):
            chunk = pids[i:i + 150]
            vals = " ".join('"' + p.replace('"', '') + '"' for p in chunk)
            query = ("SELECT ?d ?p ?mgp ?birth ?orcid WHERE { VALUES ?d { %s } ?p wdt:P2456 ?d . "
                     "OPTIONAL { ?p wdt:P549 ?mgp } OPTIONAL { ?p wdt:P569 ?birth } OPTIONAL { ?p wdt:P496 ?orcid } }" % vals)
            body = get("https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query}),
                       accept="application/sparql-results+json", delay=5)
            if body is None: raise SystemExit("wikidata query failed; rerun to resume")
            agg = {}
            for b in json.loads(body)["results"]["bindings"]:
                d = b["d"]["value"]; a = agg.setdefault(d, {"dblp_pid": d, "qid": b["p"]["value"].rsplit("/", 1)[-1], "mgp": [], "birth": [], "orcid": []})
                for k in ("mgp", "birth", "orcid"):
                    if k in b and b[k]["value"] not in a[k]: a[k].append(b[k]["value"])
            for a in agg.values(): out.write(json.dumps(a) + "\n")
            for p in chunk: q.write(p + "\n")
            out.flush(); q.flush()
            print(f"  {i + len(chunk)}/{len(pids)}: {len(agg)} with Wikidata items", flush=True)
            time.sleep(2)


def known_ids():
    """person -> (orcids, mgp ids) from DBLP, Wikidata and zbMATH author profiles."""
    import hashlib
    wd = wd_rows()
    out = {}
    for r in persons():
        orc = set(filter(None, [r["orcid"]])); mgp = set(filter(None, [r["mgp_id"]]))
        w = wd.get(r["dblp_pid"])
        if w: orc |= set(w["orcid"]); mgp |= set(w["mgp"])
        zf = f"{RAW}/zbmath/{hashlib.md5(r['person'].encode()).hexdigest()[:16]}.json"
        if os.path.exists(zf):
            ext = json.load(open(zf)).get("external_ids") or {}
            orc |= set(filter(None, [ext.get("orcid")])); mgp |= set(filter(None, [ext.get("mgp")]))
        out[r["person"]] = (sorted(orc), sorted(m for m in mgp if m.isdigit()))
    return out


def cmd_orcid():
    os.makedirs(ORCID_DIR, exist_ok=True)
    ids = sorted({o for orc, _ in known_ids().values() for o in orc})
    todo = [o for o in ids if not os.path.exists(f"{ORCID_DIR}/{o}.json")]
    print(f"{len(ids)} ORCIDs, {len(todo)} to fetch")
    for n, o in enumerate(todo):
        body = get(f"https://pub.orcid.org/v3.0/{o}/activities", accept="application/json")
        with open(f"{ORCID_DIR}/{o}.json", "w") as f: f.write(body or "{}")
        if n % 100 == 0: print(f"  {n}/{len(todo)}", flush=True)
        time.sleep(0.25)


DEGREE = re.compile(r'<span style="margin-right: 0.5em">(.*?)<span style="color:\s*#006633; margin-left: 0.5em">(.*?)</span>\s*(\d{4})?', re.S)
THESIS = re.compile(r'<span style="font-style:italic" id="thesisTitle">(.*?)</span>', re.S)


def parse_mgp(page):
    txt = lambda s: html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()
    degs = [{"degree": txt(m.group(1)), "inst": txt(m.group(2)), "year": int(m.group(3)) if m.group(3) else None}
            for m in DEGREE.finditer(page)]
    t = THESIS.search(page)
    return {"degrees": degs, "thesis": " ".join(txt(t.group(1)).split()) if t else ""}


def cmd_mgp():
    os.makedirs(MGP_DIR, exist_ok=True)
    ids = sorted({m for _, mg in known_ids().values() for m in mg}, key=int)
    todo = [m for m in ids if not os.path.exists(f"{MGP_DIR}/{m}.json")]
    print(f"{len(ids)} MGP ids, {len(todo)} to fetch (10 s crawl delay)", flush=True)
    for n, m in enumerate(todo):
        page = get(f"https://www.mathgenealogy.org/id.php?id={m}", delay=10)
        rec = parse_mgp(page) if page else {"degrees": [], "thesis": "", "error": "fetch failed"}
        with open(f"{MGP_DIR}/{m}.json", "w") as f: json.dump(rec, f)
        if n % 20 == 0: print(f"  {n}/{len(todo)}", flush=True)
        time.sleep(10)


if __name__ == "__main__":
    {"wikidata": cmd_wikidata, "orcid": cmd_orcid, "mgp": cmd_mgp}[sys.argv[1]]()
