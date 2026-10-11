#!/usr/bin/env python3
"""Author map, step 1: resolve included items to DBLP person identities and
collect each person's whole-career DBLP output.

Two streaming passes over the DBLP dump (data/raw/dblp/dblp.xml.gz):

  match   Find the DBLP record for every included/borderline item (by DBLP key,
          ePrint id, DOI, then normalized title + year +-1) and build the DBLP
          alias map (secondary name -> primary name) from person records.
          -> data/raw/dblp/authors_match.json

  stats   For every DBLP person who authored a matched item, plus DBLP names
          that are candidate matches for author strings on unmatched items,
          count all publications by year and venue type, and keep the person
          record (aliases, affiliation notes, ORCID, Math Genealogy id).
          -> data/raw/dblp/authors_stats.json

Usage: python3 -I pipeline/authors_dblp.py match|stats
"""
import gzip, re, json, sys, os, collections, unicodedata, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xml.etree.ElementTree import XMLParser

DUMP = "data/raw/dblp/dblp.xml.gz"
OUT_MATCH = "data/raw/dblp/authors_match.json"
OUT_STATS = "data/raw/dblp/authors_stats.json"
PUB_KINDS = {"article", "inproceedings", "incollection", "phdthesis", "mastersthesis", "book", "proceedings"}
CRYPTO_VENUE = re.compile(r"CRYPTO|EUROCRYPT|ASIACRYPT|PKC|TCC|CHES|PQCrypto|SAC|ANTS|J\. Cryptol|Des\. Codes Cryptogr|IACR Trans|CT-RSA|INDOCRYPT|AFRICACRYPT|LATINCRYPT|Math\. Cryptol|Cryptogr\. Commun|WCC|IMACC|ACISP|ICISC|Inscrypt|IWSEC|ProvSec|CANS|ACNS|ESORICS|IACR Commun", re.I)
INLINE = {"i", "sub", "sup", "tt", "b", "u", "em", "ref"}
EPRINT_EE = re.compile(r"eprint\.iacr\.org/(\d{4})/(\d+)")


def norm_title(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def strip_homonym(name):
    return re.sub(r"\s+\d{4}$", "", name)


def name_key(name):
    """Coarse key for fuzzy person matching: ascii last name + first initial."""
    n = unicodedata.normalize("NFKD", strip_homonym(name)).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[^a-z\s\-]", " ", n).replace("-", " ").split()
    if not n: return ""
    return f"{n[-1]}|{n[0][0]}"


def full_norm(name):
    """Exact-match key: ascii lowercase tokens of the name without DBLP homonym number or dots."""
    n = unicodedata.normalize("NFKD", strip_homonym(name)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z\s\-]", " ", n).replace("-", " ").split())


def load_entities():
    ent = {}
    for m in re.finditer(r'<!ENTITY\s+(\w+)\s+"&#(\d+);"\s*>', open("data/raw/dblp/dblp.dtd", encoding="latin-1").read()):
        ent[m.group(1)] = chr(int(m.group(2)))
    return ent


def target_items():
    """Included + borderline items (all rounds), minus manual exclusions."""
    excl = set(json.load(open("data/manual_exclusions.json"))["items"])
    files = ["data/labeled_final.jsonl", "data/phase1/labeled_final.jsonl", "data/phase1/round2/labeled_final.jsonl"]
    study = {}
    for f in files:
        if not os.path.exists(f): continue
        for l in open(f):
            r = json.loads(l); study[r.get("id") or r.get("eprint_id")] = r
    from symmetric_labels import join  # the symmetric extension's labels (notes/symmetric_extension.md)
    for r in list(study.values()) + join(study)[1]:
            rid = r.get("id") or r.get("eprint_id")
            if rid in excl or r["label"].get("include") not in ("yes", "borderline"): continue
            ids = set(r.get("all_ids") or []) | {rid}
            if r.get("eprint_id"): ids.add(r["eprint_id"])
            if r.get("eprint_match"): ids.add(r["eprint_match"])
            yield {"id": rid, "ids": sorted(ids), "title": r.get("title") or "", "year": r.get("year"),
                   "doi": (r.get("doi") or "").lower(), "authors": r.get("authors") or []}


class Stream:
    """Minimal record-level callback over the dump; cb(rec) per publication or person record."""
    def __init__(self, cb):
        self.cb = cb; self.cur = None; self.text = ""; self.attr = {}; self.n = 0
    def start(self, tag, attrib):
        if self.cur is None and (tag in PUB_KINDS or tag == "www"):
            self.cur = {"kind": tag, "key": attrib.get("key", ""), "publtype": attrib.get("publtype", ""),
                        "authors": [], "orcids": {}, "title": "", "year": None, "venue": "", "dois": [], "ees": [],
                        "notes": [], "urls": []}
        if tag not in INLINE: self.text = ""; self.attr = attrib
    def data(self, d): self.text += d
    def end(self, tag):
        c = self.cur
        if c is None or tag in INLINE: return
        t = self.text.strip()
        if tag == "author":
            c["authors"].append(t)
            if self.attr.get("orcid"): c["orcids"][t] = self.attr["orcid"]
        elif tag == "title": c["title"] = re.sub(r"\s+", " ", self.text).strip().rstrip(".")
        elif tag == "year": c["year"] = int(t) if t.isdigit() else None
        elif tag in ("journal", "booktitle", "school", "publisher") and not c["venue"]: c["venue"] = t
        elif tag == "ee":
            c["ees"].append(t)
            if "doi.org/" in t: c["dois"].append(t.split("doi.org/")[-1].lower())
        elif tag == "note" and self.attr.get("type") == "affiliation": c["notes"].append(t)
        elif tag == "url": c["urls"].append(t)
        elif tag == c["kind"]:
            self.n += 1
            if self.n % 1000000 == 0: print(f"  {self.n} records", flush=True)
            self.cb(c); self.cur = None
        self.text = ""


def run(cb):
    s = Stream(cb)
    p = XMLParser(target=s, encoding="ISO-8859-1"); p.entity.update(load_entities())
    with gzip.open(DUMP, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk: break
            p.feed(chunk)
    p.close()
    return s.n


def cmd_match():
    items = list(target_items())
    by_key, by_ep, by_doi, by_title = {}, {}, {}, collections.defaultdict(list)
    for it in items:
        for i in it["ids"]:
            if i.startswith("dblp:"): by_key[i[5:]] = it["id"]
            elif re.fullmatch(r"\d{4}/\d+", i): by_ep[i] = it["id"]
        if it["doi"]: by_doi[it["doi"]] = it["id"]
        nt = norm_title(it["title"])
        if len(nt) >= 20: by_title[nt].append(it)
    print(f"{len(items)} target items; {len(by_key)} dblp keys, {len(by_ep)} eprint ids, {len(by_doi)} dois, {len(by_title)} titles")
    hits = collections.defaultdict(list)  # item id -> [(method, dblp key, authors, publtype, venue)]
    alias = {}
    def cb(c):
        if c["kind"] == "www":
            if c["key"].startswith("homepages/") and len(c["authors"]) > 1:
                for a in c["authors"][1:]: alias[a] = c["authors"][0]
            return
        rec = (c["key"], c["authors"], c["publtype"], c["venue"], c["year"])
        if c["key"] in by_key: hits[by_key[c["key"]]].append(("key",) + rec)
        for ee in c["ees"]:
            m = EPRINT_EE.search(ee)
            if m:
                eid = f"{m.group(1)}/{int(m.group(2)):03d}"
                if eid in by_ep: hits[by_ep[eid]].append(("eprint",) + rec)
        for d in c["dois"]:
            if d in by_doi: hits[by_doi[d]].append(("doi",) + rec)
        nt = norm_title(c["title"])
        for it in by_title.get(nt, ()):
            if it["year"] is None or c["year"] is None or abs(int(str(it["year"])[:4]) - c["year"]) <= 1:
                hits[it["id"]].append(("title",) + rec)
    n = run(cb)
    json.dump({"items": items, "hits": hits, "alias": alias}, open(OUT_MATCH, "w"))
    print(f"parsed {n}; items with any DBLP hit: {len(hits)}/{len(items)}; aliases {len(alias)}")


def pick(item_hits, item_authors=()):
    """Choose the DBLP record whose author list best represents the item: most surname+initial
    overlap with the item's own author list (DBLP's ePrint entries can carry a stale first-version
    list), then key > eprint > doi > title, then peer-reviewed over informal. Returns None if the
    item lists authors and no record shares at least half of them."""
    if not item_hits: return None
    order = {"key": 0, "eprint": 1, "doi": 2, "title": 3}
    ik = {name_key(a) for a in item_authors} - {""}
    def ov(h):
        hk = {name_key(a) for a in h[2]} - {""}
        return len(ik & hk) / max(len(ik), len(hk), 1) if ik else 1.0
    best = sorted(item_hits, key=lambda h: (-ov(h), order[h[0]], h[3] == "informal", -len(h[2])))[0]
    return best if ov(best) >= 0.5 else None


def item_people(it, hits, canon, resolve):
    """[(person, method)] for an item: DBLP record authors, plus any item author the record lacks
    (resolved individually); every author resolved individually when no record is picked."""
    h = pick(hits, it["authors"])
    out = []
    if h and h[2]:
        out = [(canon(a), "dblp_" + h[0]) for a in h[2]]
        have = {name_key(a) for a in h[2]}
        out += [resolve(a) for a in it["authors"] if name_key(a) not in have]
    else:
        out = [resolve(a) for a in it["authors"]]
    seen = set(); uniq = []
    for p, m in out:
        if p not in seen: seen.add(p); uniq.append((p, m))
    return uniq


def cmd_stats():
    M = json.load(open(OUT_MATCH)); alias = M["alias"]
    canon = lambda a: alias.get(a, a)
    persons = set(); fuzzy_keys = set(); exact = set()
    for it in M["items"]:
        h = pick(M["hits"].get(it["id"], []), it["authors"])
        if h and h[2]: persons.update(canon(a) for a in h[2])
        have = {name_key(a) for a in (h[2] if h else [])}
        rest = [a for a in it["authors"] if name_key(a) not in have]
        fuzzy_keys.update(name_key(a) for a in rest)
        exact.update(full_norm(a) for a in rest if not re.match(r"^\w\.", a.strip()))
    fuzzy_keys.discard(""); exact.discard("")
    print(f"{len(persons)} DBLP persons from matched items; {len(fuzzy_keys)} fuzzy name keys from unmatched items")
    stats = {}   # canonical name -> {"pubs": {title hash: [first year, informal_only, crypto_venue]}, "orcid": ""}
    fuzzy = collections.defaultdict(collections.Counter)  # name_key -> Counter(canonical name -> n pubs)
    person = {}
    def cb(c):
        if c["kind"] == "www":
            if not c["key"].startswith("homepages/") or not c["authors"]: return
            p = c["authors"][0]
            if p in persons or full_norm(p) in exact:
                mg = [u.rsplit("=", 1)[-1] for u in c["urls"] if "mathgenealogy.org" in u or "genealogy.math.ndsu" in u]
                orc = [u.rsplit("/", 1)[-1] for u in c["urls"] if "orcid.org/" in u]
                person[p] = {"aliases": c["authors"][1:], "affil": c["notes"], "mgp": mg[:1], "orcid": orc[:1],
                             "dblp_pid": c["key"][len("homepages/"):]}
            return
        if c["kind"] == "proceedings" or not c["year"]: return
        # One entry per distinct title per person, so an ePrint/CoRR copy and its published
        # version count once; informal_only stays true only if no formal version was seen.
        informal = c["publtype"] == "informal" or c["key"].startswith(("journals/corr/", "journals/iacr/"))
        cv = bool(CRYPTO_VENUE.search(c["venue"] or ""))
        th = hashlib.md5(norm_title(c["title"]).encode()).hexdigest()[:10]
        for a in c["authors"]:
            p = canon(a)
            if p in persons or full_norm(p) in exact:
                s = stats.setdefault(p, {"pubs": {}, "orcid": ""})
                e = s["pubs"].get(th)
                if e is None: s["pubs"][th] = [c["year"], informal, cv]
                else: e[0] = min(e[0], c["year"]); e[1] = e[1] and informal; e[2] = e[2] or cv
                if a in c["orcids"]: s["orcid"] = c["orcids"][a]
            k = name_key(a)
            if k in fuzzy_keys: fuzzy[k][p] += 1
    n = run(cb)
    json.dump({"stats": stats, "person": person, "fuzzy": fuzzy}, open(OUT_STATS, "w"))
    print(f"parsed {n}; stats for {len(stats)} persons; person records {len(person)}; fuzzy keys seen {len(fuzzy)}")


if __name__ == "__main__":
    {"match": cmd_match, "stats": cmd_stats}[sys.argv[1]]()
