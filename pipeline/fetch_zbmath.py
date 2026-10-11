#!/usr/bin/env python3
"""zbMATH Open harvest by query string (MSC + title/keyword). Output JSONL.

Usage: fetch_zbmath.py OUTDIR [CLASS]   (CLASS: harvest only that class's queries)"""
import sys, os, json, time, hashlib, urllib.request, urllib.parse, urllib.error
UA = {"User-Agent": "bits-of-work-symmetric-extension/0.1 (John Servil; mailto:johnservil@proton.me; https://github.com/johnservil)"}
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
QUERIES = {
 "ecdlp": ["\"elliptic curve discrete logarithm\"", "\"Weil descent\"", "\"index calculus\" & cc:94A60", "\"anomalous\" & \"elliptic\" & cc:94A60",
           "\"discrete logarithm\" & \"elliptic\" & cc:94A60", "\"discrete logarithm\" & cc:11Y16", "ti:\"elliptic curve discrete logarithm\"", "ti:\"Weil descent\"", "ti:\"summation polynomial\"", "ti:\"index calculus\"",
           "cc:94A60 & ti:\"discrete logarithm\"", "cc:11G20 & ti:\"discrete logarithm\"", "cc:14G50 & ti:\"discrete logarithm\"",
           "cc:94A60 & ti:\"elliptic\" & ti:\"attack\"", "ti:\"anomalous\" & ti:\"elliptic\"", "ti:\"Pollard\""],
 "lattice": ["\"learning with errors\"", "\"lattice reduction\" & cc:94A60", "\"shortest vector problem\"", "\"closest vector problem\"", "\"NTRU\"", "cc:94A60 & ti:\"learning with errors\"", "cc:94A60 & ti:\"lattice\" & (ti:\"attack\" | ti:\"cryptanalysis\" | ti:\"reduction\")",
             "ti:\"shortest vector\"", "ti:\"lattice reduction\"", "ti:\"BKZ\"", "ti:\"sieving\" & ti:\"lattice\"", "ti:\"NTRU\"", "ti:\"ideal lattice\""],
 "code": ["\"information set decoding\"", "\"syndrome decoding\" & cc:94A60", "\"McEliece\"", "\"Goppa\" & cc:94A60", "ti:\"information set decoding\"", "ti:\"syndrome decoding\"", "ti:\"McEliece\"", "ti:\"Goppa\" & cc:94A60", "ti:\"low weight\" & ti:\"codeword\"", "ti:\"quasi-cyclic\" & cc:94A60"],
 "comparator": ["\"number field sieve\"", "\"factorization\" & cc:11Y05 & cc:94A60", "ti:\"number field sieve\"", "ti:\"integer factorization\"", "cc:11Y05", "ti:\"isogen\" & cc:94A60", "ti:\"multivariate\" & cc:94A60 & (ti:\"attack\" | ti:\"cryptanalysis\")"],
 # symmetric extension (notes/symmetric_preregistration.md)
 "symmetric": ["\"differential cryptanalysis\"", "\"linear cryptanalysis\"", "ti:\"block cipher\"", "ti:\"stream cipher\"",
               "ti:\"hash function\" & cc:94A60", "ti:\"cryptanalysis\" & cc:94A60", "ti:\"attack\" & cc:94A60",
               "ti:\"collision\" & ti:\"hash\"", "ti:\"preimage\"", "ti:\"S-box\" & cc:94A60", "ti:\"Boolean function\" & ti:\"correlation\""],
}
ONLY = sys.argv[2] if len(sys.argv) > 2 else None
assert ONLY is None or ONLY in QUERIES, f"unknown class {ONLY}"
def get(url, tries=8):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404: return {"result": []}  # zbMATH answers 404 for no hits / past the last page
            time.sleep(min(300, 5 * 2 ** i)); print("retry", i, e, flush=True)
        except Exception as e:
            time.sleep(min(300, 5 * 2 ** i)); print("retry", i, e, flush=True)
    raise SystemExit("giving up on " + url)  # never record a truncated query as complete
for cls, qs in QUERIES.items():
    if ONLY and cls != ONLY: continue
    for q in qs:
        fn = os.path.join(OUT, f"zb_{cls}_{hashlib.md5(q.encode()).hexdigest()[:8]}.jsonl")
        if os.path.exists(fn): continue
        page = 0; n = 0
        with open(fn + ".part", "w") as f:
            while True:
                j = get(f"https://api.zbmath.org/v1/document/_search?search_string={urllib.parse.quote(q)}&page={page}&results_per_page=100")
                if not j.get("result"): break
                for d in j["result"]:
                    row = {"zbmath_id": d.get("identifier") or d.get("id"), "doi": next((l["identifier"] for l in d.get("links", []) if l.get("type") == "doi"), ""),
                           "title": (d.get("title") or {}).get("title") if isinstance(d.get("title"), dict) else d.get("title"),
                           "year": d.get("year"), "authors": [a["name"] for a in (d.get("contributors") or {}).get("authors", [])],
                           "venue": (d.get("source") or {}).get("series", [{}])[0].get("title") if isinstance((d.get("source") or {}).get("series"), list) and (d.get("source") or {}).get("series") else None,
                           "msc": [c.get("code") for c in d.get("msc", [])], "keywords": d.get("keywords", []),
                           "abstract": " ".join(e.get("text", "") for e in d.get("editorial_contributions", []) if e.get("text")),
                           "query": q, "cls": cls}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n"); n += 1
                total = (j.get("status") or {}).get("nr_total_results", 0)
                page += 1
                if n >= total or len(j["result"]) < 100: break
                time.sleep(0.5)
        os.replace(fn + ".part", fn)
        print(f"{cls} {q}: {n}", flush=True)
print("zbmath done", flush=True)
