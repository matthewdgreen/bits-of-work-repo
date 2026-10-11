#!/usr/bin/env python3
"""Build docs/assets/data.js for the GitHub Pages site from committed study outputs.

Stdlib only. Run from the repo root:  python3 -I pipeline/build_site_data.py
Every chart on the site reads window.SITE_DATA; rerun this after the analysis changes.
"""
from pathlib import Path
import csv, json, datetime, math

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/assets/data.js'

# Site class keys -> (label, export weight columns, fte_by_year prefix)
CLASSES = [
    ('lattice',   'All lattices',       ['w_MLWE_structured', 'w_LWE_plain'], 'Lat(any)'),
    ('ecdlp',     'ECDLP',              ['w_ECDLP'],                          'ECDLP'),
    ('code',      'Syndrome decoding',  ['w_SD_code'],                        'SD'),
    ('factoring', 'Factoring / FF-DLP', ['w_Factoring_FFDLP'],                'Fact/FFDLP'),
    ('isogeny',   'Isogenies',          ['w_Isogeny'],                        'Isog'),
    ('mq',        'Multivariate',       ['w_Multivariate'],                   'MQ'),
]
SUBCLASSES = [('mlwe', 'MLWE / structured', 'MLWE'), ('lwe', 'Plain LWE', 'LWE')]
SUB_COLS = {'mlwe': ['w_MLWE_structured'], 'lwe': ['w_LWE_plain']}
EFFORT_CATS = set('ABCDEFH')  # same inclusion rule as analysis/phase1_counts.py
Y0, Y1 = 1970, 2026


PEER_KINDS = {'journal', 'conference', 'workshop'}


def peer_reviewed_ids():
    """Counted ids that appeared in a refereed journal or conference (data/venues/published_venues.csv).

    refereed = yes (registered venue) or likely (refereed by source record type, venue not registered),
    and venue_kind journal/conference/workshop. Theses, book chapters, preprints and unresolved items
    are excluded. Venue quality is not assessed.
    """
    p = ROOT / 'data/venues/published_venues.csv'
    if not p.exists():
        return None
    return {r['id'] for r in csv.DictReader(p.open())
            if r['refereed'] in ('yes', 'likely') and r['venue_kind'] in PEER_KINDS}


def paper_counts():
    """Full-corpus totals and dated chart series have deliberately different scopes."""
    rows = list(csv.DictReader((ROOT / 'data/export/combined_included.csv').open()))
    groups = [(k, cols) for k, _, cols, _ in CLASSES] + list(SUB_COLS.items())
    peer = peer_reviewed_ids()
    views = ('all', 'vetted') + (('peer',) if peer is not None else ())
    out = {v: {k: [0.0] * (Y1 - Y0 + 1) for k, _ in groups} for v in views}
    # the same series split by the classifier's quantum flag (quantum algorithms or resource estimates as the main point)
    out_q = {v: {q: {k: [0.0] * (Y1 - Y0 + 1) for k, _ in groups} for q in ('quantum', 'classical')} for v in views}
    totals = {v: {k: [] for k, _ in groups} for v in out}
    counts = {'export_total': len(rows),
              'included': sum(r['include'] == 'yes' for r in rows),
              'borderline': sum(r['include'] == 'borderline' for r in rows),
              'effort_items': 0, 'effort_without_chart_year': 0}
    for r in rows:
        if r['include'] != 'yes' or r['category'] not in EFFORT_CATS:
            continue
        counts['effort_items'] += 1
        counts['effort_works'] = counts.get('effort_works', 0) + (float(r.get('version_weight') or 1) > 0)
        y = int(r['year']) if r['year'] else None
        chart_year = y is not None and Y0 <= y <= Y1
        counts['effort_without_chart_year'] += not chart_year
        q = 'quantum' if r.get('quantum') == 'True' else 'classical'
        for key, cols in groups:
            w = sum(float(r[c] or 0) for c in cols)
            totals['all'][key].append(w)
            if chart_year:
                out['all'][key][y - Y0] += w
                out_q['all'][q][key][y - Y0] += w
            if r['vetted'] == 'True':
                totals['vetted'][key].append(w)
                if chart_year:
                    out['vetted'][key][y - Y0] += w
                    out_q['vetted'][q][key][y - Y0] += w
            if peer is not None and r['id'] in peer:
                totals['peer'][key].append(w)
                if chart_year:
                    out['peer'][key][y - Y0] += w
                    out_q['peer'][q][key][y - Y0] += w
    series = {v: {k: [round(x, 2) for x in s] for k, s in d.items()} for v, d in out.items()}
    series_q = {v: {q: {k: [round(x, 2) for x in s] for k, s in d.items()} for q, d in dq.items()} for v, dq in out_q.items()}
    totals = {v: {k: math.fsum(s) for k, s in d.items()} for v, d in totals.items()}
    return series, series_q, totals, counts


def fte():
    rows = list(csv.DictReader((ROOT / 'data/authors/fte_by_year.csv').open()))
    rows = [r for r in rows if Y0 <= int(r['year']) <= Y1]
    series = {}
    for key, _, _, pre in CLASSES + [(k, l, None, p) for k, l, p in SUBCLASSES]:
        series[key] = {
            'fte': [float(r[pre + '_fte_total']) for r in rows],
            'fte_cum': [float(r[pre + '_fte_cumulative']) for r in rows],
            'py': [float(r[pre + '_person_years']) for r in rows],
            'py_cum': [float(r[pre + '_person_years_cumulative']) for r in rows],
            'active': [int(r[pre + '_active_people']) for r in rows],
        }
    return series


# Problem literature estimates use the paper's category priors. They are not an
# audited estimate of human work before each AI result: AI flags and dates still
# require review. Priced successful-run means exclude failed and unpriced runs.
PROBLEMS = [
    # key, label, group, disclosed_run_usd (Astra costs are derived below)
    ('hawk',      'HAWK key recovery',  'crypto',    100000),
    ('erdos-1',   'Erdős #1',           'astra',     None),
    ('erdos-74',  'Erdős #74',          'astra',     None),
    ('erdos-126', 'Erdős #126',         'astra',     None),
    ('erdos-548', 'Erdős #548',         'astra',     None),
    ('erdos-571', 'Erdős #571',         'astra',     None),
    ('erdos-12',  'Erdős #12',          'alphaproof', None),
    ('erdos-26',  'Erdős #26',          'alphaproof', None),
    ('erdos-125', 'Erdős #125',         'alphaproof', None),
    ('erdos-138', 'Erdős #138',         'alphaproof', None),
    ('erdos-152', 'Erdős #152',         'alphaproof', None),
    ('erdos-741', 'Erdős #741',         'alphaproof', None),
    ('erdos-846', 'Erdős #846',         'alphaproof', None),
    ('UGC',       'Unique Games',       'openai',    None),
    ('2to1',      '2-to-1 Games',       'openai',    None),
    ('erdos-1003', 'Erdős #1003', 'unsolved', None), ('erdos-1083', 'Erdős #1083', 'unsolved', None),
    ('erdos-1206', 'Erdős #1206', 'unsolved', None), ('erdos-172', 'Erdős #172', 'unsolved', None),
    ('erdos-28', 'Erdős #28', 'unsolved', None), ('erdos-324', 'Erdős #324', 'unsolved', None),
    ('erdos-41', 'Erdős #41', 'unsolved', None), ('erdos-68', 'Erdős #68', 'unsolved', None),
    ('erdos-713', 'Erdős #713', 'unsolved', None), ('erdos-970', 'Erdős #970', 'unsolved', None),
]


PRIORS = {'A': (1, 2), 'C': (1, 2), 'F': (1, 2), 'H': (1, 2), 'D': (.5, 1.5), 'E': (2, 10), 'S': (.5, 1)}
ASTRA_MODEL = 'GPT-6 Astra (pre-release)'


def estimate(key):
    """PLAN section 8 per-paper priors; borderline at half weight (as paper/generate_tables.py)."""
    lo = hi = ai_lo = ai_hi = 0.0
    included_items = ai_items = 0
    for line in (ROOT / f'data/ai_effort/calib/{key}/labeled_final.jsonl').read_text().splitlines():
        row = json.loads(line)
        lab = row.get('label') or row
        if lab.get('include') not in ('yes', 'borderline') or lab.get('category') not in PRIORS:
            continue
        w = float(lab.get('weight') or 0) * (0.5 if lab['include'] == 'borderline' else 1)
        a, b = PRIORS[lab['category']]
        lo += w * a
        hi += w * b
        included_items += 1
        if lab.get('ai_assisted'):
            ai_lo += w * a
            ai_hi += w * b
            ai_items += 1
    return {'py': (lo + hi) / 2, 'py_lo': lo, 'py_hi': hi,
            'ai_flagged_py': (ai_lo + ai_hi) / 2,
            'ai_flagged_items': ai_items, 'included_items': included_items,
            'temporal_audit': 'not_audited'}


def successful_run_costs():
    """Average disclosed priced successes, including #1's over-cap resolution.

    These are conditional successful-run costs, not campaign costs per result.
    The CSV does not disclose individual costs for most unsuccessful attempts.
    """
    costs = {}
    successes = {'resolved', 'resolved_but_not_counted_in_score'}
    with (ROOT / 'data/ai_effort/erdos_problems.csv').open() as f:
        for row in csv.DictReader(f):
            if (row['model'] == ASTRA_MODEL and row['outcome'] in successes
                    and row['cost_usd']):
                key = 'erdos-' + row['problem_number']
                costs.setdefault(key, []).append(float(row['cost_usd']))
    return costs


def problems():
    out = []
    costs = successful_run_costs()
    for key, label, group, usd in PROBLEMS:
        priced = costs.get(key, []) if group == 'astra' else []
        if priced:
            usd = math.fsum(priced) / len(priced)
        out.append({'key': key, 'label': label, 'group': group, **estimate(key),
                    'ai_usd': round(usd, 2) if usd is not None else None,
                    'ai_priced_successes': len(priced) if priced else None,
                    'ai_cost_basis': ('mean_disclosed_successful_run' if priced else
                                      'disclosed_run' if usd is not None else 'not_disclosed'),
                    'ai_cost_includes_failed_runs': False if priced else None})
    return out


# Frontier gaps: analysis/records_normalized.md ("Frontier vs deployed targets").
GAPS = [
    {'target': 'RSA-2048', 'cls': 'factoring', 'lo': 35.02, 'hi': 35.02, 'vs': 'RSA-896 (2026)',
     'approx': True, 'basis': 'Leading-term GNFS ratio; about 35 billion times modeled work, not a runtime or dollar forecast.'},
    {'target': 'ML-KEM-512', 'cls': 'lattice', 'lo': 60, 'hi': 75, 'vs': 'SVP challenge, sieving dim 171 (2026)',
     'basis': 'Per sieve call; excludes repeated calls in the full attack. Range varies the sieving slope, not a confidence interval.'},
    {'target': 'HQC-128', 'cls': 'code', 'lo': 61, 'hi': 61, 'vs': 'QC decoding n=4098 (2026)', 'approx': True,
     'basis': 'Prange iteration ratio with a 7-bit quasi-cyclic discount; approximate instance comparison.'},
    {'target': 'P-256', 'cls': 'ecdlp', 'lo': 69.3, 'hi': 69.3, 'vs': '117-bit generic ECDLP (2016)',
     'basis': 'Generic Pollard-rho group-operation model; operation and implementation costs vary between curves.'},
    {'target': 'mceliece348864', 'cls': 'code', 'lo': 79, 'hi': 79, 'vs': 'Goppa decoding n=1409 (2023)',
     'basis': 'Decoding-challenge work-factor scale, using proxy target n=3471.'},
    {'target': 'ML-KEM-768', 'cls': 'lattice', 'lo': 121, 'hi': 152, 'vs': 'SVP challenge, sieving dim 171 (2026)',
     'basis': 'Per sieve call; excludes repeated calls in the full attack. Range varies the sieving slope, not a confidence interval.'},
]


def attack_history():
    """analysis/attack_stability.py -> data/export/attack_history.json (selected bounds and qualitative events)."""
    return json.loads((ROOT / 'data/export/attack_history.json').read_text())


def main():
    paper_series, paper_series_q, paper_totals, corpus_counts = paper_counts()
    data = {
        'generated': datetime.date.today().isoformat(),
        'years': list(range(Y0, Y1 + 1)),
        'classes': [{'key': k, 'label': l} for k, l, *_ in CLASSES],
        'subclasses': [{'key': k, 'label': l} for k, l, _ in SUBCLASSES],
        'papers': paper_series,
        'papers_q': paper_series_q,
        'paper_totals': paper_totals,
        'corpus_counts': corpus_counts,
        'source_labels': {'all': 'All sources', 'vetted': 'ePrint / DBLP subset', 'peer': 'Peer-reviewed venue'},
        'fte': fte(),
        'problems': problems(),
        'gaps': GAPS,
        'attack_history': attack_history(),
        'effort_proxy': {
            'unit': 'publication-based research-allocation years',
            'measured_hours': False,
            'nominal_hours_per_year': 2000,
            'caveat': 'Publication shares proxy time allocation. Missing total-output data can assign a whole research-year to a briefly studied topic; the totals may substantially overestimate actual time. Adjacent work or classification errors can also inflate them.',
        },
        'usd_per_year': 250000,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('// Generated by pipeline/build_site_data.py; do not edit.\n'
                   'window.SITE_DATA = ' + json.dumps(data, separators=(',', ':'), ensure_ascii=False) + ';\n')
    print(f'wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
