#!/usr/bin/env python3
"""OpenAlex harvest, credit-aware.

OpenAlex (2026) meters requests in credits per day: search = 10 credits/page,
filter list = 1 credit/page, singleton GET /works/{id} = 0 credits; unkeyed
budget is 1000/day (x-ratelimit-* headers). So: singletons are used wherever
possible (seed resolution by DOI, backward snowball), list pages only for
forward citations and phrase search, and the harvester sleeps until the
budget resets instead of failing. If ~/.openalex_key exists (one line) it is
sent as api_key and never printed.

Usage:
  fetch_openalex.py phrases  OUTDIR [CLASS]                 # CLASS: harvest only that class's phrases
  fetch_openalex.py resolve  SEEDS.jsonl OUTDIR   # rows with "seed_id" and "doi" and/or "openalex_id"
  fetch_openalex.py backward OUTDIR               # singleton fetch of every work referenced by the seeds
  fetch_openalex.py forward  OUTDIR [max_citers_per_seed]
Outputs (JSONL of trimmed work objects): phrase_<cls>_<md5>.jsonl, snow_seeds.jsonl,
snow_backward.jsonl, snow_forward.jsonl; progress in *_done.json files.
"""
import sys, os, re, json, time, hashlib, urllib.request, urllib.parse, urllib.error
MAILTO = "johnservil@proton.me"
UA = {"User-Agent": f"bits-of-work-symmetric-extension/0.1 (John Servil; mailto:{MAILTO}; https://github.com/johnservil)"}
BASE = "https://api.openalex.org/works"
FIELDS = "id,doi,title,publication_year,publication_date,type,authorships,primary_location,abstract_inverted_index,referenced_works,cited_by_count,ids"
KEYFILE = os.path.expanduser("~/.openalex_key")
budget = {"remaining": None, "reset": None}

def api_key():
    try: return open(KEYFILE).read().strip() or None
    except OSError: return None

def wait_for_reset(why):
    secs = int(budget["reset"] or 3600) + 60
    print(f"budget exhausted ({why}); sleeping {secs}s until reset", flush=True)
    while secs > 0:  # wake hourly to pick up a newly added key
        step = min(secs, 3600); time.sleep(step); secs -= step
        if api_key() and secs > 0: print("api key appeared; resuming", flush=True); return

def get(url, cost=1, tries=12):
    """cost = credits this request needs; waits for reset if the budget can't cover it."""
    for i in range(tries):
        if cost and budget["remaining"] is not None and budget["remaining"] < cost:
            wait_for_reset(f"remaining {budget['remaining']} < {cost}"); budget["remaining"] = None
        key = api_key()
        full = url + ("&" if "?" in url else "?") + "mailto=" + MAILTO + (f"&api_key={key}" if key else "")
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers=UA), timeout=90) as r:
                h = r.headers
                if h.get("x-ratelimit-remaining") is not None:
                    budget["remaining"] = int(h["x-ratelimit-remaining"]); budget["reset"] = int(h.get("x-ratelimit-reset") or 3600)
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code == 429:
                ra = int(e.headers.get("Retry-After", 0) or 0)
                budget["reset"] = int(e.headers.get("x-ratelimit-reset") or ra or 3600)
                if ra and ra < 120: time.sleep(ra); continue
                if not cost: time.sleep(min(600, 30 * 2 ** i)); continue  # free endpoint: per-second throttle
                budget["remaining"] = 0; continue
            wait = min(600, 10 * 2 ** i); print(f"retry {i} HTTP {e.code}; sleeping {wait}s", flush=True); time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as e:
            wait = min(600, 5 * 2 ** i); print(f"retry {i} {type(e).__name__}; sleeping {wait}s", flush=True); time.sleep(wait)
    raise SystemExit("giving up on " + url)  # url never contains the key

def abstract(inv):
    if not inv: return ""
    pos = {}
    for w, ps in inv.items():
        for p in ps: pos[p] = w
    return " ".join(pos[i] for i in sorted(pos))

def trim(w):
    return {"openalex_id": w["id"].rsplit("/", 1)[-1], "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "title": w.get("title") or "", "year": w.get("publication_year"), "date": w.get("publication_date"),
            "type": w.get("type"),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author")],
            "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
            "abstract": abstract(w.get("abstract_inverted_index")),
            "referenced_works": [r.rsplit("/", 1)[-1] for r in w.get("referenced_works", [])],
            "cited_by_count": w.get("cited_by_count")}

def single(ident):
    """Free singleton GET; ident is an OpenAlex id (W...) or 'doi:10.x/...'."""
    j = get(f"{BASE}/{urllib.parse.quote(ident, safe=':/')}?select={FIELDS}", cost=0)
    time.sleep(0.12)
    return trim(j) if j and j.get("id") else None

def paged(filter_, out, cost, limit=None):
    """Page through a list query; resumable at page granularity via OUT.cursor so
    a killed harvester never re-pays for pages it already wrote."""
    part, cur = out + ".part", out + ".cursor"
    cursor, n = "*", 0
    if os.path.exists(part) and os.path.exists(cur):
        st = json.load(open(cur)); cursor, n = st["cursor"], st["n"]
        with open(part, "r+") as f:  # drop any lines written after the last saved cursor
            lines = f.readlines()[:n]; f.seek(0); f.writelines(lines); f.truncate()
        print(f"  resuming {os.path.basename(out)} at {n} rows", flush=True)
    else:
        open(part, "w").close()
    with open(part, "a") as f:
        while cursor:
            j = get(f"{BASE}?filter={urllib.parse.quote(filter_, safe=':,|')}&select={FIELDS}&per-page=200&cursor={cursor}", cost=cost)
            for w in j["results"]:
                f.write(json.dumps(trim(w), ensure_ascii=False) + "\n"); n += 1
            cursor = j["meta"].get("next_cursor") if j["results"] else None
            f.flush(); json.dump({"cursor": cursor, "n": n}, open(cur, "w"))
            if limit and n >= limit: break
            time.sleep(0.2)
    os.replace(part, out)
    if os.path.exists(cur): os.remove(cur)
    return n

def qfile(out, cls, q): return os.path.join(out, f"phrase_{cls}_{hashlib.md5(q.encode()).hexdigest()[:8]}.jsonl")

# Ordered by value: ECDLP and code history are the classes ePrint covers worst.
PHRASES = {
 "ecdlp": ['"elliptic curve discrete logarithm"', '"Weil descent"', '"summation polynomial"', '"index calculus"',
           '"anomalous elliptic curve"', '"Pollard rho"', '"Pollard kangaroo"', '"Koblitz curve" attack', '"generic group" "discrete logarithm"',
           '"ECDLP"', '"hyperelliptic" "discrete logarithm"', '"MOV attack"', '"Frey-Rück"'],
 "code": ['"information set decoding"', '"syndrome decoding"', '"McEliece" attack', '"McEliece" cryptanalysis', '"Goppa" distinguisher',
          '"low weight codeword"', '"quasi-cyclic" attack', '"MDPC" attack', '"HQC" attack', '"BIKE" attack', '"learning parity with noise"'],
 "lattice": ['"learning with errors" attack', '"learning with errors" cryptanalysis', '"lattice sieving"', '"BKZ"', '"lattice reduction" cryptanalysis',
             '"shortest vector problem" algorithm', '"ideal lattice" attack', '"NTRU" attack', '"NTRU" cryptanalysis', '"dual attack" lattice',
             '"primal attack"', '"BKW" LWE', '"Arora-Ge"', '"SVP challenge"', '"LWE challenge"', '"Kyber" security', '"lattice enumeration"'],
 "comparator": ['"number field sieve"', '"integer factorization" algorithm', '"RSA" factoring record', '"SIDH" attack', '"SIKE" attack',
                '"supersingular isogeny" attack', '"isogeny" cryptanalysis', '"CSIDH" attack',
                '"Rainbow" cryptanalysis', '"multivariate" cryptanalysis', '"HFE" attack', '"MinRank"'],
 # symmetric extension (notes/symmetric_preregistration.md)
 "symmetric": ['"differential cryptanalysis"', '"linear cryptanalysis"', '"impossible differential"', '"differential-linear"',
               '"boomerang attack"', '"integral attack"', '"cube attack"', '"division property"', '"rebound attack"',
               '"related-key attack"', '"slide attack"', '"meet-in-the-middle attack" cipher', '"algebraic attack" cipher',
               '"correlation attack"', '"guess-and-determine"', '"distinguishing attack"', '"key recovery attack" cipher',
               '"block cipher" cryptanalysis', '"stream cipher" cryptanalysis', '"hash function" cryptanalysis',
               '"collision attack" hash', '"preimage attack"', '"time-memory trade-off" attack', '"Grover" "block cipher"'],
}

def load_ids(path):
    return {json.loads(l)["openalex_id"] for l in open(path)} if os.path.exists(path) else set()

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "phrases":
        out = sys.argv[2]; os.makedirs(out, exist_ok=True)
        only = sys.argv[3] if len(sys.argv) > 3 else None
        assert only is None or only in PHRASES, f"unknown class {only}"
        for cls, qs in PHRASES.items():
            if only and cls != only: continue
            for q in qs:
                fn = qfile(out, cls, q)
                if os.path.exists(fn): continue
                n = paged(f"title_and_abstract.search:{q}", fn, cost=10)
                print(f"{cls} {q}: {n} (budget left {budget['remaining']})", flush=True)
        print("phrases done", flush=True)
    elif mode == "resolve":
        seeds, out = sys.argv[2], sys.argv[3]; os.makedirs(out, exist_ok=True)
        sf = os.path.join(out, "snow_seeds.jsonl"); dp = os.path.join(out, "resolve_done.json")
        done = json.load(open(dp)) if os.path.exists(dp) else {}
        rows = [json.loads(l) for l in open(seeds)]; hit = 0
        with open(sf, "a") as f:
            for k, r in enumerate(rows):
                if r["seed_id"] in done: continue
                w = None
                if r.get("openalex_id"): w = single(r["openalex_id"])
                if not w and r.get("doi"): w = single("doi:" + r["doi"].lower())
                if not w and r.get("title"):  # last resort: title search (10 credits)
                    t = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]+", " ", r["title"])).strip()[:150]
                    rt = re.sub(r"[^a-z0-9]+", "", r["title"].lower())[:40]
                    if len(t) >= 8:
                        j = get(f"{BASE}?filter=title.search:{urllib.parse.quote(t)}&select=id,title&per-page=5", cost=10)
                        for c in (j or {}).get("results", []):
                            if re.sub(r"[^a-z0-9]+", "", (c.get("title") or "").lower())[:40] == rt:
                                w = single(c["id"].rsplit("/", 1)[-1]); break
                if w:
                    w["seed_id"] = r["seed_id"]; f.write(json.dumps(w, ensure_ascii=False) + "\n"); hit += 1
                done[r["seed_id"]] = w["openalex_id"] if w else None
                if k % 100 == 0: json.dump(done, open(dp, "w")); f.flush(); print(f"  resolve {k}/{len(rows)}", flush=True)
        json.dump(done, open(dp, "w"))
        print(f"resolved {sum(1 for v in done.values() if v)}/{len(done)} seeds", flush=True)
    elif mode == "backward":
        out = sys.argv[2]; sf = os.path.join(out, "snow_seeds.jsonl"); bf = os.path.join(out, "snow_backward.jsonl")
        refs = sorted({x for l in open(sf) for x in json.loads(l)["referenced_works"]})
        have = load_ids(bf) | load_ids(sf); todo = [x for x in refs if x not in have]
        print(f"backward: {len(refs)} referenced works, {len(todo)} to fetch (batched, 1 credit per 50)", flush=True)
        with open(bf, "a") as f:
            for i in range(0, len(todo), 50):
                j = get(f"{BASE}?filter=openalex_id:{'|'.join(todo[i:i+50])}&select={FIELDS}&per-page=50", cost=1)
                for w in (j or {}).get("results", []): f.write(json.dumps(trim(w), ensure_ascii=False) + "\n")
                f.flush(); time.sleep(0.15)
                if i % 2500 == 0: print(f"  backward {i}/{len(todo)} (budget left {budget['remaining']})", flush=True)
        print("backward done", flush=True)
    elif mode == "dois":
        # batched DOI lookup: 50 DOIs per filter page = 1 credit; resumable via dois_done.json
        doifile, out = sys.argv[2], sys.argv[3]; of = os.path.join(out, "doi_lookup.jsonl"); dp = os.path.join(out, "dois_done.json")
        dois = sorted({l.strip().lower() for l in open(doifile) if l.strip()})
        done = set(json.load(open(dp))) if os.path.exists(dp) else set()
        todo = [d for d in dois if d not in done and "|" not in d and "," not in d]
        print(f"dois: {len(dois)} total, {len(todo)} to fetch", flush=True)
        with open(of, "a") as f:
            for i in range(0, len(todo), 50):
                chunk = todo[i:i+50]
                j = get(f"{BASE}?filter=doi:{'|'.join(urllib.parse.quote(d, safe='/:') for d in chunk)}&select={FIELDS}&per-page=50", cost=1)
                for w in (j or {}).get("results", []): f.write(json.dumps(trim(w), ensure_ascii=False) + "\n")
                f.flush(); done.update(chunk); json.dump(sorted(done), open(dp, "w")); time.sleep(0.15)
                if i % 2500 == 0: print(f"  dois {i}/{len(todo)} (budget left {budget['remaining']})", flush=True)
        print("dois done", flush=True)
    elif mode == "forward":
        out = sys.argv[2]; cap = int(sys.argv[3]) if len(sys.argv) > 3 else 400
        sf = os.path.join(out, "snow_seeds.jsonl"); ff = os.path.join(out, "snow_forward.jsonl"); dp = os.path.join(out, "forward_done.json")
        ids = sorted({json.loads(l)["openalex_id"] for l in open(sf)})
        done = set(json.load(open(dp))) if os.path.exists(dp) else set()
        with open(ff, "a") as f:
            for k, sid in enumerate(ids):
                if sid in done: continue
                cursor = "*"; n = 0
                while cursor and n < cap:
                    j = get(f"{BASE}?filter=cites:{sid}&select={FIELDS}&per-page=200&cursor={cursor}", cost=1)
                    for w in j["results"]: w = trim(w); w["cites_seed"] = sid; f.write(json.dumps(w, ensure_ascii=False) + "\n"); n += 1
                    cursor = j["meta"].get("next_cursor") if j["results"] else None; time.sleep(0.2)
                f.flush(); done.add(sid); json.dump(sorted(done), open(dp, "w"))
                if k % 50 == 0: print(f"  forward {k}/{len(ids)} (budget left {budget['remaining']})", flush=True)
        print("forward done", flush=True)
