#!/usr/bin/env python3
"""Author map: who did the public cryptanalysis, how much of their output it was,
and how the per-class author networks look and overlap.

Inputs: data/export/combined_included.csv (labels, class weights),
        data/raw/dblp/authors_match.json + authors_stats.json (pipeline/authors_dblp.py).
Outputs: data/authors/authors.csv          one row per person
         data/authors/authorships.csv      one row per (person, item)
         data/authors/coauthor_edges.csv   one row per coauthor pair, class-weighted
         analysis/author_map.txt           summary tables (stdout)

Identity: DBLP persons (homonym-disambiguated, aliases merged). Items DBLP lacks are
resolved by exact full name to a unique DBLP person, or by surname + initial to a
unique person already in the cryptanalysis set; otherwise the author string is
kept as an unresolved identity ("name:<normalized>").

Effort model (research-FTE): for person p, year y, class c,
  share_c(y) = sum of class-c weights of p's included items in [y-2, y+2]
               / max(p's distinct DBLP publications in [y-2, y+2], that numerator total)
  FTE_c(y)   = share_c(y), summed over persons -> research-FTE in class c in year y.
Persons without a DBLP record get the per-paper prior (PLAN section 8, proxy 1)
instead. Both are reported side by side.
"""
import csv, json, re, sys, collections, unicodedata, math, os
sys.path.insert(0, "pipeline")
from authors_dblp import pick, item_people, name_key, full_norm, strip_homonym, OUT_MATCH, OUT_STATS

POL = json.load(open("pipeline/attribution.json"))
CLASSES = POL["classes"]; EFF = set(POL["effort_categories"])
SHOW = CLASSES[:2] + ["Lattice_any"] + CLASSES[2:]
SHORT = {"Symmetric": "Sym", "ECDLP": "ECDLP", "MLWE_structured": "MLWE", "Lattice_any": "Lat(any)", "LWE_plain": "LWE",
         "SD_code": "SD", "Factoring_FFDLP": "Fact/FFDLP", "Isogeny": "Isog", "Multivariate": "MQ"}
PY_PRIOR = {"A": 1.5, "C": 1.5, "F": 1.5, "D": 1.0, "E": 6.0, "B": 1.5, "H": 0.75}  # PY per paper, midpoints of PLAN ranges
NOW = 2026
WIN = 2
# Floor on a person's total output rate (pubs/year) in the share denominator. DBLP misses much of
# mathematicians' output and has gaps, so without a floor a person with 4 DBLP papers over 11 years
# would be counted as 11 full research years of cryptanalysis. With rate 1.0 one paper is worth at
# most one research-FTE-year. Override: --rate=X
CENSOR = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--censor=")), 1))
RATE = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--rate=")), 1.0))
USE_ZB = "--no-zbmath" not in sys.argv
# Share of working time spent on research, by career stage (priors; see analysis/author_map_method.md).
# Converts research-FTE (share of output) into calendar person-years.
RESEARCH_FRACTION = {"student": 0.9, "early": 0.85, "established_academic": 0.45,
                     "established_nonacademic": 0.7, "established_unknown": 0.5}
EARLY_YEARS = 5   # years after the PhD counted as early career (postdoc / junior)
STAGES = ["student", "early", "established"]

# ---------- load ----------
labels = {r["id"]: r for r in csv.DictReader(open("data/export/combined_included.csv"))}
M = json.load(open(OUT_MATCH)); S = json.load(open(OUT_STATS))
alias = M["alias"]; stats = S["stats"]; person = S["person"]; fuzzy = S["fuzzy"]
canon = lambda a: alias.get(a, a)
import hashlib
def zb_docs(p):
    f = f"data/raw/enrich/zbmath/{hashlib.md5(p.encode()).hexdigest()[:16]}.json"
    return (json.load(open(f)).get("docs") or []) if USE_ZB and os.path.exists(f) else []
CAREER = {r["person"]: r for r in csv.DictReader(open("data/authors/career.csv"))} if os.path.exists("data/authors/career.csv") else {}
def employment_sector(p, y):
    best = None
    for e in (CAREER.get(p, {}).get("employments") or "").split("; "):
        if not e: continue
        span, sector = e.split(":")[0], e.split(":")[1]
        a, b = span.split("-")
        a = int(a) if a else 0; b = int(b) if b else NOW
        if a <= y <= b and (best is None or a >= best[0]): best = (a, sector)
    return best[1] if best else "unknown"
def stage(p, y):
    """-> (stage label for reporting, research fraction)"""
    phd = CAREER.get(p, {}).get("phd_year")
    if phd and y < int(phd): return "student", RESEARCH_FRACTION["student"]
    if phd and y < int(phd) + EARLY_YEARS: return "early", RESEARCH_FRACTION["early"]
    return "established", RESEARCH_FRACTION["established_" + employment_sector(p, y)]
crypto_persons = set()
for it in M["items"]:
    h = pick(M["hits"].get(it["id"], []), it["authors"])
    if h and h[2]: crypto_persons.update(canon(a) for a in h[2])
exact_index = collections.defaultdict(set)
for p in stats: exact_index[full_norm(p)].add(p)


def first_tokens_compatible(raw, cand):
    a = full_norm(raw).split(); b = full_norm(cand).split()
    if not a or not b: return False
    fa, fb = a[0], b[0]
    raw_initial = bool(re.match(r"^\s*\w\.", raw)) or len(fa) == 1
    return fa[0] == fb[0] if raw_initial else fa == fb


def resolve(raw):
    """-> (person id, method)"""
    fn = full_norm(raw)
    ex = exact_index.get(fn, set())
    if len(ex) == 1: return next(iter(ex)), "exact"
    cands = [p for p in fuzzy.get(name_key(raw), {}) if p in crypto_persons and first_tokens_compatible(raw, p)]
    if len(cands) == 1: return cands[0], "fuzzy_crypto"
    if not fn:  # non-Latin script (Japanese, Korean, Cyrillic): keep the script form as the identity
        fn = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", raw)).strip().lower()
    return "name:" + fn, "unresolved"


items = {}
authorships = []   # (pid, item id, method)
for it in M["items"]:
    L = labels.get(it["id"])
    if L is None: continue
    uniq = item_people(it, M["hits"].get(it["id"], []), canon, resolve)
    w = {c: float(L[f"w_{c}"]) for c in CLASSES}
    w["Lattice_any"] = w["MLWE_structured"] + w["LWE_plain"]
    y = str(L["year"])[:4]
    items[it["id"]] = {"year": int(y) if y.isdigit() else None, "cat": L["category"], "include": L["include"],
                       "vetted": L["vetted"] == "True", "record": L["is_record"] == "True", "w": w,
                       "n": len(uniq), "pids": [p for p, _ in uniq], "title": L["title"]}
    for p, m in uniq: authorships.append((p, it["id"], m))


def counted(i, border=False):
    return i["cat"] in EFF and (i["include"] == "yes" or (border and i["include"] == "borderline"))


# ---------- per-person profiles ----------
def career(p):
    """Distinct publications by year: DBLP and zbMATH merged on normalized-title hash."""
    s = stats.get(p) or {"pubs": {}}
    pubs = {h: v[0] for h, v in s["pubs"].items()}
    n_dblp = len(pubs)
    for d in zb_docs(p):
        if d.get("year") and d.get("th"): pubs[d["th"]] = min(pubs.get(d["th"], 9999), d["year"])
    ys = collections.Counter(y for y in pubs.values() if 1900 < y <= NOW)
    if not ys: return None
    inf = sum(v[1] for v in s["pubs"].values()); cv = sum(v[2] for v in s["pubs"].values())
    return {"by_year": ys, "n": sum(ys.values()), "n_dblp": n_dblp, "n_zb_only": len(pubs) - n_dblp,
            "first": min(ys), "last": max(ys), "informal": inf, "crypto": cv}


P = collections.defaultdict(lambda: {"items": [], "methods": collections.Counter()})
for p, iid, m in authorships:
    P[p]["items"].append(iid); P[p]["methods"][m] += 1

fte = collections.defaultdict(lambda: collections.defaultdict(float))   # class -> year -> research-FTE
fte_prior = collections.defaultdict(lambda: collections.defaultdict(float))
fte_cal = collections.defaultdict(lambda: collections.defaultdict(float))   # calendar person-years (stage-weighted)
fte_stage = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(float)))  # class -> stage -> year
rows = []
for p, d in P.items():
    its = [items[i] for i in d["items"]]
    yes = [i for i in its if counted(i)]
    car = career(p)
    r = {"person": p, "name": strip_homonym(p[5:] if p.startswith("name:") else p),
         "resolution": "dblp" if any(m.startswith("dblp_") for m in d["methods"]) else (
             "unresolved" if p.startswith("name:") else d["methods"].most_common(1)[0][0]),
         "n_items_yes": len(yes), "n_items_yes_or_borderline": sum(counted(i, True) for i in its),
         "n_vetted_yes": sum(i["vetted"] for i in yes), "n_records": sum(i["record"] for i in yes),
         "first_item": min((i["year"] for i in yes if i["year"]), default=""),
         "last_item": max((i["year"] for i in yes if i["year"]), default=""),
         "categories": " ".join(f"{k}:{v}" for k, v in sorted(collections.Counter(i["cat"] for i in yes).items()))}
    for c in SHOW:
        r[f"touch_{SHORT[c]}"] = sum(1 for i in yes if i["w"][c] > 0)
        r[f"frac_{SHORT[c]}"] = round(sum(i["w"][c] for i in yes), 3)
        r[f"credit_{SHORT[c]}"] = round(sum(i["w"][c] / i["n"] for i in yes), 3)
    fr = {c: r[f"frac_{SHORT[c]}"] for c in CLASSES}
    r["primary_class"] = max(fr, key=fr.get) if yes and max(fr.values()) > 0 else ""
    r["n_classes_touched"] = sum(1 for c in CLASSES if r[f"touch_{SHORT[c]}"] > 0)
    r["tier"] = "core" if len(yes) >= 5 else ("regular" if len(yes) >= 2 else ("occasional" if yes else "borderline_only"))
    pr = person.get(p, {})
    r.update({"dblp_pid": pr.get("dblp_pid", ""), "affiliation": "; ".join(pr.get("affil", [])[:2]),
              "orcid": (pr.get("orcid") or [stats.get(p, {}).get("orcid", "")])[0] if (pr.get("orcid") or stats.get(p, {}).get("orcid")) else "",
              "mgp_id": (pr.get("mgp") or [""])[0]})
    if car:
        r.update({"dblp_pubs": car["n_dblp"], "zbmath_only_pubs": car["n_zb_only"], "total_pubs": car["n"],
                  "dblp_first": car["first"], "dblp_last": car["last"],
                  "career_years": car["last"] - car["first"] + 1,
                  "crypto_venue_share": round(car["crypto"] / max(1, car["n_dblp"]), 3),
                  "cryptanalysis_share": round(min(1.0, len(yes) / car["n"]), 3)})
        # windowed research-FTE by class
        by_year_items = collections.defaultdict(list)
        for i in yes:
            if i["year"]: by_year_items[i["year"]].append(i)
        tot_fte = collections.defaultdict(float); tot_cal = collections.defaultdict(float)
        # A person counts until their last DBLP year. Someone whose last paper is within CENSOR years of
        # NOW is treated as still active through NOW (recent output is not indexed yet; 2026 is a part year).
        end = NOW if car["last"] >= NOW - CENSOR else car["last"]
        for y in range(car["first"], end + 1):
            den = sum(car["by_year"].get(t, 0) for t in range(y - WIN, y + WIN + 1))
            win_items = [i for t in range(y - WIN, y + WIN + 1) for i in by_year_items.get(t, [])]
            if not win_items: continue
            num_any = sum(max(i["w"][c] for c in CLASSES) for i in win_items)
            # Floor counts only window years the person could have published in (from their first
            # DBLP year up to NOW); a fixed 5-year floor depressed shares at the right edge.
            yrs = min(y + WIN, NOW) - max(y - WIN, car["first"]) + 1
            den = max(den, num_any, RATE * yrs, 1e-9)
            st, rf = stage(p, y)
            for c in SHOW:
                v = sum(i["w"][c] for i in win_items) / den
                if v:
                    fte[c][y] += v; tot_fte[c] += v
                    fte_cal[c][y] += v * rf; tot_cal[c] += v * rf; fte_stage[c][st][y] += v
        for c in SHOW:
            r[f"fte_years_{SHORT[c]}"] = round(tot_fte[c], 3)
            r[f"person_years_{SHORT[c]}"] = round(tot_cal[c], 3)
    else:
        for c in SHOW:
            v = 0.0
            for i in yes:
                x = i["w"][c] * PY_PRIOR.get(i["cat"], 1.0) / i["n"]
                v += x
                if i["year"]:  # same +-WIN window as the DBLP-share model, so the two parts are comparable
                    for t in range(i["year"] - WIN, min(i["year"] + WIN, NOW) + 1):
                        x_t = x / (min(i["year"] + WIN, NOW) - (i["year"] - WIN) + 1)
                        fte_prior[c][t] += x_t; fte_cal[c][t] += x_t; fte_stage[c]["unknown"][t] += x_t
            r[f"fte_years_{SHORT[c]}"] = round(v, 3)
            r[f"person_years_{SHORT[c]}"] = round(v, 3)  # the per-paper prior is already in person-years
    r["fte_basis"] = "pub_share" if car else "per_paper_prior"
    rows.append(r)

rows.sort(key=lambda r: (-r["n_items_yes"], r["name"]))
os.makedirs("data/authors", exist_ok=True)
cols = list(dict.fromkeys(k for r in rows for k in r))
with open("data/authors/authors.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
with open("data/authors/authorships.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["person", "item_id", "resolution", "year", "include", "category", "n_authors"] + [f"w_{SHORT[c]}" for c in SHOW] + ["title"])
    for p, iid, m in authorships:
        i = items[iid]
        w.writerow([p, iid, m, i["year"], i["include"], i["cat"], i["n"]] + [round(i["w"][c], 3) for c in SHOW] + [i["title"]])
edges = collections.defaultdict(lambda: collections.defaultdict(float))
for iid, i in items.items():
    if not counted(i): continue
    ps = sorted(i["pids"])
    for a in range(len(ps)):
        for b in range(a + 1, len(ps)):
            e = edges[(ps[a], ps[b])]; e["n"] += 1
            for c in SHOW: e[c] += 1 if i["w"][c] > 0 else 0
with open("data/authors/coauthor_edges.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["a", "b", "n_items"] + [f"n_{SHORT[c]}" for c in SHOW])
    for (a, b), e in sorted(edges.items()): w.writerow([a, b, int(e["n"])] + [int(e[c]) for c in SHOW])

# ---------- summary ----------
out = []
pr = out.append
yes_rows = [r for r in rows if r["n_items_yes"] > 0]
pr(f"AUTHOR MAP (include = yes, effort categories A-F,H; output-rate floor {RATE} pubs/yr; generated by analysis/author_map.py)\n")
inc = [(p, m) for p, iid, m in authorships if counted(items[iid])]
mc = collections.Counter(m for _, m in inc)
pr(f"Authorships (person x item) on included items: {len(inc)}; resolution: " + ", ".join(f"{k} {v} ({v/len(inc):.1%})" for k, v in mc.most_common()))
pr(f"Distinct persons with >=1 included item: {len(yes_rows)}  (with DBLP/zbMATH career data: {sum(1 for r in yes_rows if r['fte_basis']=='pub_share')}; unresolved strings: {sum(1 for r in yes_rows if r['resolution']=='unresolved')})")
pr(f"Tiers: " + ", ".join(f"{t} {n}" for t, n in collections.Counter(r['tier'] for r in yes_rows).most_common()))
pr("")

# per-class headline
pr("Per class: persons by tier (by in-class item count), concentration, network, research-FTE-years")
pr(f"{'class':10s} {'persons':>7s} {'1 item':>6s} {'2-4':>5s} {'5+':>4s} {'top10%cr':>8s} {'n50%cr':>6s} {'comps':>5s} {'LCC%':>5s} {'groups3+':>8s} {'FTE-yrs':>8s} {'prior-yrs':>9s} {'FTE/item':>8s}")
def components(nodes, adj):
    seen = set(); comps = []
    for n in sorted(nodes):
        if n in seen: continue
        st = [n]; seen.add(n); comp = []
        while st:
            x = st.pop(); comp.append(x)
            for y in adj[x]:
                if y in nodes and y not in seen: seen.add(y); st.append(y)
        comps.append(comp)
    return comps
def label_prop(nodes, adj, wt):
    lab = {n: n for n in nodes}
    for _ in range(30):
        ch = 0
        for n in sorted(nodes):
            sc = collections.Counter()
            for y in adj[n]:
                if y in nodes: sc[lab[y]] += wt[frozenset((n, y))]
            if sc:
                best = max(sorted(sc), key=lambda k: sc[k])
                if best != lab[n]: lab[n] = best; ch += 1
        if not ch: break
    return collections.Counter(lab.values())
class_sets = {}
for c in SHOW:
    k = SHORT[c]
    members = [r for r in yes_rows if r[f"touch_{k}"] > 0]
    class_sets[c] = {r["person"] for r in members}
    tiers = collections.Counter(1 if r[f"touch_{k}"] == 1 else (2 if r[f"touch_{k}"] < 5 else 5) for r in members)
    cr = sorted((r[f"credit_{k}"] for r in members), reverse=True); tot = sum(cr) or 1
    top10 = sum(cr[:max(1, len(cr) // 10)]) / tot
    acc = 0; n50 = 0
    for x in cr:
        acc += x; n50 += 1
        if acc >= tot / 2: break
    adj = collections.defaultdict(set); wt = collections.Counter()
    for (a, b), e in edges.items():
        if e[c] > 0: adj[a].add(b); adj[b].add(a); wt[frozenset((a, b))] = e[c]
    comps = components(class_sets[c], adj)
    lcc = max((len(x) for x in comps), default=0)
    groups = sum(1 for v in label_prop(class_sets[c], adj, wt).values() if v >= 3)
    fy = sum(r.get(f"fte_years_{k}", 0) for r in members if r["fte_basis"] == "pub_share")
    py = sum(r.get(f"fte_years_{k}", 0) for r in members if r["fte_basis"] != "pub_share")
    nitems = sum(i["w"][c] for i in items.values() if counted(i))
    pr(f"{k:10s} {len(members):7d} {tiers[1]:6d} {tiers[2]:5d} {tiers[5]:4d} {top10:8.1%} {n50:6d} {len(comps):5d} {lcc/max(1,len(members)):5.0%} {groups:8d} {fy:8.1f} {py:9.1f} {(fy+py)/max(nitems,1e-9):8.2f}")
pr("  persons = distinct people with >=1 item touching the class; 1 item / 2-4 / 5+ = their in-class item counts;")
pr("  top10%cr = share of author-fractional credit held by the top 10% of persons; n50%cr = persons holding 50% of credit;")
pr("  comps/LCC% = coauthor-graph components and largest-component share; groups3+ = label-propagation communities of >=3;")
pr("  FTE-yrs = summed research-FTE-years from DBLP output shares (windowed +-2 yrs); prior-yrs = per-paper prior for persons")
pr("  without DBLP data; FTE/item = research-FTE-years per fractional item.\n")

pr("Vetted view (items in ePrint or DBLP only; drops OpenAlex/zbMATH-only items, where low-quality venues concentrate)")
pr(f"{'class':10s} {'persons':>7s} {'1 item':>6s} {'2-4':>5s} {'5+':>4s}")
vc = collections.defaultdict(collections.Counter)
for p, iid, m in authorships:
    i = items[iid]
    if counted(i) and i["vetted"]:
        for c in SHOW:
            if i["w"][c] > 0: vc[c][p] += 1
for c in SHOW:
    t = collections.Counter(1 if n == 1 else (2 if n < 5 else 5) for n in vc[c].values())
    pr(f"{SHORT[c]:10s} {len(vc[c]):7d} {t[1]:6d} {t[2]:5d} {t[5]:4d}")
pr("")

pr("Overlap: persons active in row class who are also active in column class (share of row)")
pr(f"{'':10s} " + " ".join(f"{SHORT[c]:>9s}" for c in SHOW))
for a in SHOW:
    pr(f"{SHORT[a]:10s} " + " ".join(f"{len(class_sets[a] & class_sets[b]) / max(1, len(class_sets[a])):9.0%}" for b in SHOW))
pr("")
pr("Overlap among regulars (>=2 in-class items in both classes): counts")
reg = {c: {r['person'] for r in yes_rows if r[f'touch_{SHORT[c]}'] >= 2} for c in SHOW}
pr(f"{'':10s} " + " ".join(f"{SHORT[c]:>9s}" for c in SHOW))
for a in SHOW:
    pr(f"{SHORT[a]:10s} " + " ".join(f"{len(reg[a] & reg[b]):9d}" for b in SHOW))
pr("")

pr("Research-FTE by year (DBLP-share model + per-paper prior for persons without DBLP data), 5-year bins, mean FTE per year")
bins = [(1975, 1989), (1990, 1999), (2000, 2005), (2006, 2010), (2011, 2016), (2017, 2021), (2022, 2026)]
pr(f"{'class':10s} " + " ".join(f"{f'{a}-{b%100:02d}':>9s}" for a, b in bins))
for c in SHOW:
    pr(f"{SHORT[c]:10s} " + " ".join(f"{sum(fte[c][y] + fte_prior[c][y] for y in range(a, b + 1)) / (b - a + 1):9.1f}" for a, b in bins))
pr("")
# Every-year series: data/authors/fte_by_year.csv (one row per year, per class: DBLP-share FTE,
# per-paper-prior FTE for people without DBLP data, total, and distinct active people).
act_y = collections.defaultdict(lambda: collections.defaultdict(set))
for p_, iid, m in authorships:
    i = items[iid]
    if counted(i) and i["year"]:
        for c in SHOW:
            if i["w"][c] > 0:
                for y in range(i["year"], i["year"] + 3): act_y[c][y].add(p_)
with open("data/authors/fte_by_year.csv", "w", newline="") as f:
    w = csv.writer(f)
    KEYS = ("fte_share", "fte_prior", "fte_total", "fte_cumulative", "person_years", "person_years_cumulative",
            "fte_student", "fte_early", "fte_established", "fte_unknown_stage", "active_people")
    w.writerow(["year"] + [f"{SHORT[c]}_{k}" for c in SHOW for k in KEYS])
    cum = collections.defaultdict(float); cumc = collections.defaultdict(float)
    for y in range(min(min(fte[c]) for c in SHOW if fte[c]), NOW + 1):
        for c in SHOW: cum[c] += fte[c][y] + fte_prior[c][y]; cumc[c] += fte_cal[c][y]
        if y < 1970: continue
        w.writerow([y] + [v for c in SHOW for v in (
            round(fte[c][y], 2), round(fte_prior[c][y], 2), round(fte[c][y] + fte_prior[c][y], 2), round(cum[c], 1),
            round(fte_cal[c][y], 2), round(cumc[c], 1),
            round(fte_stage[c]["student"][y], 2), round(fte_stage[c]["early"][y], 2),
            round(fte_stage[c]["established"][y], 2), round(fte_stage[c]["unknown"][y], 2), len(act_y[c][y]))])
pr("Research-FTE by year (people-equivalents: each person counts as the share of their output in the class, +-2-yr window).")
pr("Right edge: the floor counts only available window years and people active in NOW-1 are carried to NOW; 2026 is a part year and its window is one-sided, so treat it as noisier.")
pr(f"{'year':6s} " + " ".join(f"{SHORT[c]:>9s}" for c in SHOW))
for y in range(1985, NOW + 1):
    pr(f"{y:<6d} " + " ".join(f"{fte[c][y] + fte_prior[c][y]:9.1f}" for c in SHOW))
pr("")

pr("Career-stage composition of research-FTE (share of class FTE from PhD students / early career (<5 yrs after PhD) /")
pr("established researchers / per-paper-prior people of unknown stage), and calendar person-years (stage-weighted)")
pr(f"{'class':10s} {'period':9s} {'student':>8s} {'early':>6s} {'estab.':>7s} {'unknown':>8s}  {'FTE/yr':>7s} {'cal.PY/yr':>9s}")
for c in SHOW:
    for a, b in [(2006, 2016), (2017, 2021), (2022, 2026)]:
        tot = sum(fte[c][y] + fte_prior[c][y] for y in range(a, b + 1)) or 1e-9
        part = {st: sum(fte_stage[c][st][y] for y in range(a, b + 1)) / tot for st in STAGES + ["unknown"]}
        cal = sum(fte_cal[c][y] for y in range(a, b + 1)) / (b - a + 1)
        pr(f"{SHORT[c]:10s} {a}-{b%100:02d}  {part['student']:8.0%} {part['early']:6.0%} {part['established']:7.0%} {part['unknown']:8.0%}  {tot/(b-a+1):7.1f} {cal:9.1f}")
pr(f"Cumulative to {NOW}: research-FTE-years vs calendar person-years")
for c in SHOW:
    pr(f"  {SHORT[c]:10s} {sum(fte[c].values()) + sum(fte_prior[c].values()):8.0f} {sum(fte_cal[c].values()):8.0f}")
pr(f"  research fractions used: {RESEARCH_FRACTION}; early career = {EARLY_YEARS} yrs after PhD")
pr("")

pr("Active persons by year (distinct people with an in-class item in the trailing 3 years), selected years")
YS = [1995, 2000, 2005, 2010, 2015, 2020, 2023, 2026]
pr(f"{'class':10s} " + " ".join(f"{y:>6d}" for y in YS))
act = collections.defaultdict(lambda: collections.defaultdict(set))
for p, iid, m in authorships:
    i = items[iid]
    if not counted(i) or not i["year"]: continue
    for c in SHOW:
        if i["w"][c] > 0:
            for y in range(i["year"], i["year"] + 3): act[c][y].add(p)
for c in SHOW:
    pr(f"{SHORT[c]:10s} " + " ".join(f"{len(act[c][y]):6d}" for y in YS))
pr("")

pr("Career profile of persons by primary class (medians; persons with DBLP/zbMATH career data)")
def med(v): v = sorted(v); return v[len(v) // 2] if v else 0
pr(f"{'class':10s} {'n':>5s} {'dblp pubs':>9s} {'all pubs':>8s} {'career yrs':>10s} {'crypt.share':>11s} {'crypto-venue':>12s}")
for c in CLASSES:
    g = [r for r in yes_rows if r["primary_class"] == c and r["fte_basis"] == "pub_share"]
    pr(f"{SHORT[c]:10s} {len(g):5d} {med([r['dblp_pubs'] for r in g]):9d} {med([r['total_pubs'] for r in g]):8d} {med([r['career_years'] for r in g]):10d} {med([r['cryptanalysis_share'] for r in g]):11.2f} {med([r['crypto_venue_share'] for r in g]):12.2f}")
pr("")

for c in SHOW:
    k = SHORT[c]
    top = sorted((r for r in yes_rows if r[f"touch_{k}"] > 0), key=lambda r: -r[f"credit_{k}"])[:25]
    pr(f"Top 25 by author-fractional credit: {k}")
    pr(f"  {'name':30s} {'credit':>6s} {'items':>5s} {'yrs':>9s} {'FTEyrs':>6s} {'share':>5s}  affiliation")
    for r in top:
        pr(f"  {r['name'][:30]:30s} {r[f'credit_{k}']:6.2f} {r[f'touch_{k}']:5d} {str(r['first_item'])+'-'+str(r['last_item']):>9s} {r.get(f'fte_years_{k}',0):6.1f} {r.get('cryptanalysis_share',''):>5}  {r['affiliation'][:45]}")
    pr("")
print("\n".join(out))
