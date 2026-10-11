"""Join the symmetric extension's labels to the study's (notes/symmetric_extension.md).

The study's labels supply every public-key weight; ours supply only the symmetric
weight. join(study) takes the study's labeled rows as {id: row} and returns:

  study  the same rows, where a row we also labeled and the study credits to a
         public-key class gets the tag `symmetric` with weight min(our symmetric
         share, the share the study's label leaves to no class), taken from that
         unassigned share, so its public-key weights stay exactly as they were;
  extra  our other included rows, as new rows whose tags are {"symmetric": s,
         "other": 1 - s}: their public-key tags are dropped.

Our rows match study rows by id or by normalized title; round-1 and round-2 rows
whose ePrint version is in our ePrint round are dropped as duplicates.
"""
import json, re

LABELS = "data/symmetric/labeled_final.jsonl"
POL = json.load(open("pipeline/attribution.json")); FRAC = POL["fractional"]

def norm(t): return re.sub(r"[^a-z0-9]+", "", (t or "").lower())[:60]

def shares(L):
    tags = L.get("problem_tags") or {}; tot = sum(tags.values()) or 1.0
    return {t: w / tot for t, w in tags.items()}

def assigned(sh): return sum(w for t, w in sh.items() if FRAC.get(t))

def join(study):
    ours = [json.loads(l) for l in open(LABELS)]
    ep_ids = {r["id"] for r in ours if r["round"] == "eprint"}
    by_title = {}
    for sid, r in study.items(): by_title.setdefault(norm(r.get("title")), sid)
    study = dict(study); extra = []
    for r in ours:
        if r["round"] != "eprint" and r.get("eprint_match") in ep_ids: continue
        L = r["label"]
        if L.get("include") not in ("yes", "borderline"): continue
        s = shares(L).get("symmetric", 0.0)
        if s == 0: continue
        sid = r["id"] if r["id"] in study else by_title.get(norm(r.get("title")))
        S = study.get(sid)
        if S and S["label"].get("include") in ("yes", "borderline") and assigned(shares(S["label"])) > 0:
            sh = shares(S["label"]); free = 1.0 - assigned(sh); add = min(s, free)
            if add <= 0: continue
            tags = {t: (w if FRAC.get(t) else w * (1 - add / free)) for t, w in sh.items()}
            tags["symmetric"] = add
            S = dict(S); S["label"] = dict(S["label"], problem_tags=tags); study[sid] = S
        else:
            row = dict(r); row["label"] = dict(L, problem_tags={"symmetric": s, "other": 1.0 - s} if s < 1 else {"symmetric": 1.0})
            extra.append(row)
    return study, extra
