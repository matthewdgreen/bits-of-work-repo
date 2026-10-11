#!/usr/bin/env python3
"""Stream-parse the DBLP XML dump (gzip) and emit keyword-screened candidates.

Keeps every record whose title matches the Phase-0 keyword patterns (title
only, since DBLP has no abstracts), plus ALL records from a venue allowlist
(so venue-level recall can be measured). Output: data/raw/dblp/dblp_candidates.jsonl
"""
import gzip, re, json, sys, collections, importlib.util
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import XMLParser

SRC = sys.argv[1]; OUT = sys.argv[2]
src = open("pipeline/candidates.py").read().split("counts = collections.Counter()")[0]
ns = {}; exec(src, ns); PC = ns["PC"]

VENUES = re.compile(r"CRYPTO|FSE|EUROCRYPT|ASIACRYPT|PKC|TCC|CHES|PQCrypto|SAC|ANTS|J\. Cryptol|Des\. Codes Cryptogr|Math\. Comput|LMS J\. Comput\. Math|Adv\. Math\. Commun|IACR Trans|CT-RSA|INDOCRYPT|AFRICACRYPT|LATINCRYPT|ACNS|ESORICS|CCS|S&P|USENIX Security|IEEE Trans\. Inf\. Theory|ISIT|WCC|Finite Fields|J\. Number Theory|Math\. Cryptol|Cryptogr\. Commun", re.I)
KINDS = {"article", "inproceedings", "incollection", "phdthesis", "book"}

# DBLP needs its DTD for entities; use a parser with the DTD loaded.
class Target:
    def __init__(self, out):
        self.out = out; self.stack = []; self.cur = None; self.n = 0; self.kept = 0; self.text = ""; self.by_kind = collections.Counter()
    def start(self, tag, attrib):
        if tag in KINDS and self.cur is None:
            self.cur = {"kind": tag, "key": attrib.get("key"), "authors": [], "title": "", "year": None, "venue": "", "doi": "", "ee": ""}
        self.stack.append(tag); self.text = ""
    def data(self, d): self.text += d
    def end(self, tag):
        self.stack.pop()
        c = self.cur
        if c is not None:
            if tag == "author": c["authors"].append(self.text.strip())
            elif tag == "title": c["title"] = re.sub(r"\s+", " ", self.text).strip().rstrip(".")
            elif tag == "year": c["year"] = int(self.text.strip()) if self.text.strip().isdigit() else None
            elif tag in ("journal", "booktitle"): c["venue"] = self.text.strip()
            elif tag == "ee" and "doi.org" in self.text: c["doi"] = self.text.strip().split("doi.org/")[-1]
            elif tag == c["kind"]:
                self.n += 1; self.by_kind[c["kind"]] += 1
                t = c["title"]
                hits = {cls: [lab for rx, lab in pats if rx.search(t)] for cls, pats in PC.items()}
                hits = {k: v for k, v in hits.items() if v}
                if hits.get("ecdlp") == ["dlog generic"] and set(hits) <= {"ecdlp", "symmetric"}: del hits["ecdlp"]
                venue_ok = bool(VENUES.search(c["venue"] or ""))
                if hits or c["kind"] == "phdthesis" or venue_ok:
                    c["kw_hits"] = hits; c["venue_allow"] = venue_ok
                    self.out.write(json.dumps(c, ensure_ascii=False) + "\n"); self.kept += 1
                self.cur = None
                if self.n % 500000 == 0: print(f"  {self.n} records, kept {self.kept}", flush=True)
    def close(self): return self.n

# expat does not read external DTDs, so load DBLP's named character entities ourselves.
ENT = {}
for m in re.finditer(r'<!ENTITY\s+(\w+)\s+"&#(\d+);"\s*>', open("data/raw/dblp/dblp.dtd", encoding="latin-1").read()):
    ENT[m.group(1)] = chr(int(m.group(2)))

with open(OUT, "w") as out:
    target = Target(out)
    parser = XMLParser(target=target, encoding="ISO-8859-1")
    parser.entity.update(ENT)
    with gzip.open(SRC, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk: break
            parser.feed(chunk)
    parser.close()
print(f"parsed {target.n} records; kept {target.kept}; by kind {dict(target.by_kind)}")
