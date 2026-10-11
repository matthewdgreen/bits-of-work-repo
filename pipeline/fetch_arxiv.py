#!/usr/bin/env python3
"""arXiv harvest via the export API (Atom). One file per query, atomic.

Usage: fetch_arxiv.py data/raw/arxiv
arXiv asks for <= 1 request per 3 s; 503s are common and retried with backoff.
"""
import sys, os, re, json, time, hashlib, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
UA = {"User-Agent": "bits-of-work-symmetric-extension/0.1 (John Servil; mailto:johnservil@proton.me; https://github.com/johnservil)"}
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom", "os": "http://a9.com/-/spec/opensearch/1.1/"}
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)

Q = {
 "ecdlp": ['abs:"elliptic curve discrete logarithm"', 'abs:ECDLP', 'abs:"Weil descent"', 'abs:"summation polynomial"',
           'abs:"index calculus"', 'abs:"Pollard rho"', 'abs:kangaroo AND abs:"discrete logarithm"',
           'abs:Shor AND abs:"elliptic curve"', 'abs:"discrete logarithm" AND abs:"elliptic"', 'abs:"generic group" AND abs:"discrete logarithm"'],
 "lattice": ['abs:"learning with errors" AND (abs:attack OR abs:cryptanalysis OR abs:solving OR abs:hardness)',
             'abs:"shortest vector problem"', 'abs:"closest vector problem"', 'abs:"lattice reduction"', 'abs:BKZ',
             'abs:"lattice sieving"', 'abs:"lattice enumeration"', 'abs:NTRU AND (abs:attack OR abs:cryptanalysis)',
             'abs:"ideal lattice"', 'abs:"bounded distance decoding"', 'abs:Kyber AND (abs:attack OR abs:security)',
             'abs:quantum AND abs:lattice AND (abs:algorithm OR abs:attack) AND cat:quant-ph'],
 "code": ['abs:"information set decoding"', 'abs:"syndrome decoding"', 'abs:McEliece', 'abs:Goppa AND (abs:attack OR abs:distinguisher OR abs:cryptanalysis)',
          'abs:"low weight codeword"', 'abs:"learning parity with noise"', 'abs:"decoding problem" AND (abs:quantum OR abs:algorithm OR abs:hardness) AND cat:cs.IT',
          'abs:"code-based" AND (abs:attack OR abs:cryptanalysis)'],
 "comparator": ['abs:"number field sieve"', 'abs:"integer factorization" AND (abs:algorithm OR abs:record OR abs:quantum)',
                'abs:Shor AND abs:factoring AND (abs:resource OR abs:estimate OR abs:qubits)', 'abs:isogeny AND (abs:attack OR abs:cryptanalysis OR abs:"key recovery")',
                'abs:SIDH', 'abs:multivariate AND (abs:cryptanalysis OR abs:attack) AND cat:cs.CR', 'abs:MinRank'],
}

def get(url, tries=10):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r: return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            wait = min(600, 15 * 2 ** i); print(f"retry {i} {e}; sleeping {wait}s", flush=True); time.sleep(wait)
    raise SystemExit("giving up on " + url)

def text(e, path):
    x = e.find(path, NS); return re.sub(r"\s+", " ", x.text).strip() if x is not None and x.text else ""

for cls, qs in Q.items():
    for q in qs:
        fn = os.path.join(OUT, f"ax_{cls}_{hashlib.md5(q.encode()).hexdigest()[:8]}.jsonl")
        if os.path.exists(fn): continue
        start, n, total = 0, 0, None
        with open(fn + ".part", "w") as f:
            while total is None or start < total:
                url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": q, "start": start, "max_results": 200, "sortBy": "submittedDate", "sortOrder": "ascending"})
                root = ET.fromstring(get(url)); time.sleep(3.5)
                total = int(text(root, "os:totalResults") or 0)
                ents = root.findall("a:entry", NS)
                if not ents and start < total:  # arXiv sometimes returns an empty page transiently
                    time.sleep(30); root = ET.fromstring(get(url)); ents = root.findall("a:entry", NS)
                    if not ents: raise SystemExit(f"empty page at {start}/{total} for {q}")
                for e in ents:
                    aid = text(e, "a:id").rsplit("/abs/", 1)[-1]
                    row = {"arxiv_id": re.sub(r"v\d+$", "", aid), "title": text(e, "a:title"), "abstract": text(e, "a:summary"),
                           "date": text(e, "a:published")[:10], "year": int(text(e, "a:published")[:4] or 0),
                           "authors": [text(a, "a:name") for a in e.findall("a:author", NS)],
                           "doi": text(e, "arxiv:doi"), "journal_ref": text(e, "arxiv:journal_ref"),
                           "categories": [c.get("term") for c in e.findall("a:category", NS)], "query": q, "cls": cls}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n"); n += 1
                start += 200
                if start >= 10000: print(f"  capped at 10000 for {q}", flush=True); break
        os.replace(fn + ".part", fn)
        print(f"{cls} {q}: {n} of {total}", flush=True)
print("arxiv done", flush=True)
