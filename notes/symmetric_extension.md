# Symmetric extension: what we changed, and why

This repository adds one assumption class, **Symmetric** (cryptanalysis of block ciphers, stream ciphers, hash functions, MACs, and permutations), to the study as Matthew Green published it. This note records every change to the study's code, data, and method, so its authors and anyone else can see what differs, check it, reproduce it, or vary it.

- **Baseline:** commit `172f562`, the public export from the study's private repository at `90e638c`; the study's main is merged in up to `627e384` (change 20).
- **Class definitions, fixed before measurement:** `notes/symmetric_preregistration.md` (commit `a565658`, 2026-10-10).
- **Every code change:** `git diff 172f562 -- pipeline analysis`.
- **Published at:** https://github.com/johnservil/bits-of-work-repo, branch `symmetric`; its `main` mirrors the study's.

## Result

Cumulative research-allocation years through 2026 (`data/authors/fte_by_year.csv`, `*_fte_cumulative`), from one run over every class:

| Class | Published | This run |
|---|---|---|
| ECDLP | 593.8 | 598.3 |
| All lattices | 1,036.4 | 1,043.8 |
| Syndrome decoding | 331.4 | 333.4 |
| Factoring / FF-DLP | 1,111.1 | 1,121.6 |
| Isogeny | 116.6 | 117.4 |
| Multivariate | 210.2 | 213.0 |
| **Symmetric** | | **6,677.2** |

Symmetric is about 6.4 times all lattices. By era (research-allocation years): 729 through 2005, 2,624 in 2006–2016, 3,324 in 2017–2026; 12% comes from the per-paper prior for people without DBLP records (lattices 9%, factoring 25%). Fractional paper counts (A–F, H, include = yes; `analysis/phase1_counts.txt`): 5,466 from all sources, 3,851 vetted.

## Effect on the study's existing results

Every public-key label, count, export column, and record stays as published. Rerunning the public-key keyword screen on the new ePrint harvest with our code yields the same 4,754 candidates, with the same keyword hits, as the baseline code (check below), and every public-key line of `analysis/phase1_counts.txt` is unchanged. The research-allocation series in `data/authors/fte_by_year.csv` come from our rerun of the author map and differ from the published ones by 0.6–1.3% (change 19); the website and white paper, built from that file, still show the published figures. FSE's addition to the DBLP venue lists (change 4) could add public-key candidates on a full public-key rerun, which has yet to be done.

## Changes

Each entry gives the date, the change, the reason, and its effect on the public-key classes.

1. **2026-10-10. Raw data re-harvested.** The study's raw pulls are outside the public export, and its committed ePrint file has no abstracts.
   - ePrint, via `pipeline/fetch_eprint_oai.py`: 57 OAI-PMH pages; 27,272 records after 838 deleted stubs, parsed by `pipeline/parse_eprint_oai.py` to `data/raw/eprint/eprint_oai.jsonl` (sha256 `ddf8d134eb0d5a19116312a8a8cd23743f917ef96a5a1f78435a19fa0c969308`). The committed `data/eprint.jsonl` is unchanged.
   - DBLP dump `dblp.xml.gz` downloaded 2026-10-10, 1,110,469,870 bytes (sha256 `d02df2909fc497390c78ea142bc2cc05397dcb6873161a9306c9a4e2d38e960f`), with `dblp.dtd` (sha256 `2d864498f9eef9298662df11e3874171ff24cd4a21ab5974f1369c90acdb1ef6`).
   - `pipeline/parse_dblp.py` keeps 385,011 of 8,712,838 DBLP records (the study kept 375,911); about 4,100 symmetric title hits are absent from ePrint.
   - Both pulls are one day newer than the study's; the public-key labels keep the study's pulls.
2. **2026-10-10. Harvester identity.** Every harvester (`fetch_eprint_oai.py`, `fetch_openalex.py`, `fetch_zbmath.py`, `fetch_arxiv.py`, `authors_enrich.py`) identifies this extension and John Servil (johnservil@proton.me, https://github.com/johnservil) in place of the study author's address; `fetch_openalex.py` sends that address as `mailto=`, exactly as the study sent its own. The 2026-10-10 ePrint and DBLP downloads sent `bits-of-work-symmetric-extension/0.1`. Without an API key OpenAlex allows 1,000 credits a day (the study had a key with 10,000); the address leaves that limit unchanged.
3. **2026-10-10. Symmetric keyword screen.** `pipeline/candidates.py` gains a `symmetric` class with four patterns: names of symmetric-cryptanalysis techniques (matched alone), hash-attack phrases, primitive names beside an attack word, and generic or quantum symmetric attacks. Primitive names that are also English words (PRESENT, IDEA, GIFT, Grain, SIMON, and others) match case-sensitively. On ePrint the screen yields 3,016 symmetric candidates; precision is the classifier's job, as in the study.
4. **2026-10-10. FSE added to DBLP venue lists.** `pipeline/parse_dblp.py` (`VENUES`) and `pipeline/merge_sources.py` (`CORE`) include FSE, the main symmetric venue. `IACR Trans` already covered ToSC. Effect: a full public-key rerun would also keep every FSE record and fetch FSE abstracts, which could add a few public-key candidates.
5. **2026-10-10. Weak "discrete log" rule ignores symmetric hits.** The study drops a candidate whose only hit is the generic `discrete log` keyword. A symmetric hit would have counted as a second class and kept 11 extra ePrint items as ECDLP candidates. The rule now ignores symmetric hits, in all three copies (`candidates.py`, `parse_dblp.py`, `merge_sources.py`); the public-key screen is identical to the baseline's.

6. **2026-10-10. Rubric v0.4.** `pipeline/rubric.md` gains the `symmetric` tag, worded from the pre-registration, with ten calibration examples; the out-of-scope list under `other` drops "hash/symmetric cryptanalysis". The public-key rules are unchanged, and the study's labels keep v0.3.4.
7. **2026-10-10. API classifier.** `pipeline/classify_openrouter.py` sends each batch in one OpenRouter call, with the instructions in `pipeline/classify_prompt.md` ("API pass 1/2") plus the rubric as the system message. The instructions are the study's pass-1 and pass-2 prompts, minus their file and tool steps, and minus "chaos-based image encryption" from the list of non-cryptographic papers, since the pre-registration counts such cryptanalysis. The runner checks every line and every id itself, and records each call's tokens and cost in `usage.tsv` beside the labels.
8. **2026-10-10. Symmetric searches.** `fetch_openalex.py` (24 phrases) and `fetch_zbmath.py` (11 queries) gain symmetric searches, and an optional class argument that harvests one class alone.
9. **2026-10-10. Pilot.** 60 randomly drawn ePrint symmetric candidates (seed 20261010), labeled by pass 1 with `anthropic/claude-sonnet-5.5` and the study's 1,000-character abstract cap: 34 yes (23 A, 5 C, 4 F, 2 G), 26 no; one call, 31,093 prompt and 7,075 completion tokens, $0.13. Labels: `data/symmetric/pilot_p1/`. Pools and batches embed third-party abstracts, so they stay in the gitignored `data/raw/symmetric/`, as the study's public export omits its own.

10. **2026-10-10. ePrint pass 1.** All 3,016 ePrint symmetric candidates (including the 523 that also hit a public-key class), 51 batches, `anthropic/claude-sonnet-5.5`, abstract cap 1,000: every batch valid on its first call, $6.78. Labels: `data/symmetric/eprint_p1/`. These labels serve the symmetric weight only; the public-key classes keep the study's labels.
11. **2026-10-10. ePrint pass 2.** `make_pass2.py` unchanged (seed 20261008, 10% audit of exclusions, abstract cap 1,500), `anthropic/claude-opus-5.5`: 2,145 yes/borderline items plus 87 sampled exclusions, 38 batches; passes 1 and 2 together cost $20.47. `merge_pass2.py`: include kappa 0.83, category agreement 0.94, 0 of 87 audited exclusions flipped (the study: 0.84-0.89, 0.92, 1.1%). As in the study, pass 2 sees the pass-1 label. Manifest `data/symmetric/eprint_p2_manifest.json`, labels `data/symmetric/eprint_p2/`, statistics `data/symmetric/eprint_agreement.txt`.
12. **2026-10-10. Runner retries truncated responses.** A response cut off mid-read (`http.client.IncompleteRead`) stopped the first pass-2 run after 28 of 38 batches; `classify_openrouter.py` now retries `http.client.HTTPException` like other network errors, and the rerun finished the remaining 10.

13. **2026-10-10. One screen and one merge for both tracks.** `candidates.py` and `merge_sources.py` take an optional class argument, like the harvesters. Without it they behave exactly as the study's code did, ignoring symmetric hits (`candidates.py` output matches the baseline code byte for byte on the new ePrint harvest). With `symmetric` they keep symmetric candidates only. Symmetric runs also take ePrint coverage and snowball seeds from `data/raw/symmetric/eprint_labeled_final.jsonl`, and write to `data/raw/symmetric/candidates_merged.jsonl`, `data/raw/openalex/seeds_symmetric*.jsonl` and `data/symmetric/coverage.txt`; the committed study files stay untouched. The symmetric pool is untiered, since every symmetric hit is tier A under the study's rule.
14. **2026-10-10. Merge and round 1.** OpenAlex DOI lookups (39,555 DOIs of core-venue DBLP items lacking abstracts, 39,292 works returned), then `merge_sources.py symmetric`: 9,429 screened symmetric items, 1,285 covered by the ePrint pool, 8,144 new (5,473 with abstracts). Pass 1 on the 8,144 started (`data/symmetric/r1_p1/`). Snowball: 1,428 resolved seeds plus 556 by title, then backward and forward (cap 400 citers per seed), as in `run_openalex_chain.sh`.

15. **2026-10-10. Runner restores the subagents' self-check.** In 3 of 136 round-1 batches, pass 1 left out one item on every attempt; a diagnostic call showed a normal reply with one ordinary item skipped. The study's subagents counted their lines and fixed any gap (pass-1 prompt, step 4). The runner now does the same: when a reply lacks some ids, it asks once, in the same conversation, for exactly those lines (`pipeline/classify_prompt.md` records the wording). The three batches then completed. Two diagnostic calls ($0.23) ran outside the runner and are absent from `usage.tsv`.
16. **2026-10-10. Round 1 labeled.** Pass 1, 136 batches; pass 2 (`make_pass2.py` unchanged), 4,206 yes/borderline items plus 393 sampled exclusions, 77 batches. `merge_pass2.py`: include kappa 0.84, category agreement 0.91, 2 of 393 audited exclusions flipped (estimated miss rate 0.5%). Labels `data/symmetric/r1_p1/`, `data/symmetric/r1_p2/`; manifest `data/symmetric/r1_p2_manifest.json`; statistics `data/symmetric/r1_agreement.txt`. Recorded spend through round 1: $62.48.

17. **2026-10-10. Snowball round.** Forward and backward citations of 1,728 resolved seeds (cap 400 citers each) added 698 candidates absent from round 1, matched by every identifier the merge records. Both passes: include kappa 0.88, category agreement 0.90, 0 of 31 audited exclusions flipped (`data/symmetric/r2_agreement.txt`). Recorded spend for all symmetric labeling: $66.28.
18. **2026-10-10. Symmetric labels join the study's.** `data/symmetric/labeled_final.jsonl` holds all 11,858 symmetric labels (ePrint, round 1, snowball round), abstracts stripped like the study's committed labels. `pipeline/symmetric_labels.py` joins them to the study's labels under one rule: the study's labels supply every public-key weight, ours supply only the symmetric weight. A paper both tracks credit (13 papers, mostly generic collision search) gets a symmetric weight of at most the share the study's label left to no class, so its total stays at most one paper. Round-1 and round-2 rows whose ePrint version is in our ePrint round are dropped as duplicates. `pipeline/attribution.json` gains the class `Symmetric` and the tag `symmetric` (weight 1.0). `analysis/export_combined.py`, `analysis/phase1_counts.py` and `pipeline/authors_dblp.py` read the joined labels; every public-key line of `analysis/phase1_counts.txt` is unchanged, and the export without the symmetric loader reproduces the study's committed CSV byte for byte.

19. **2026-10-10. Author map rerun with every class.** `pipeline/authors_dblp.py` match and stats on the 2026-10-10 DBLP dump (7,778 of 10,785 included items matched), `pipeline/authors_zbmath.py` (4,716 people in scope, 1,210 profiles accepted; every failed request recovered), then `analysis/author_map.py`, unchanged apart from the short name `Sym`. `data/authors/fte_by_year.csv` now comes from this one run over all classes, so the public-key series move from the published ones by 0.6–1.3% (fresher DBLP and zbMATH data); without the zbMATH step they move by 2–4%. Person-level tables stay out of git, and `analysis/author_map.txt` has its top-25 lists cut by `pipeline/export_public.py`'s own `transform`, as in the study's public export.

20. **2026-10-10. Merged the study's main at `627e384`.** Its new version weights (preprints and duplicates of a counted work 0, journal extensions 1/3; `pipeline/build_version_weights.py`) now apply to the public-key rows of the export and the counts, and every public-key line of both counts files matches the study's `627e384` byte for byte. Symmetric rows carry weight 1: the weights rest on `data/venues/duplicate_checks.csv`, whose same-work groups cover the study's labels only. They lowered the study's all-source public-key paper counts by about 3–4% (ECDLP 465.2 to 448.4). Our `data/authors/fte_by_year.csv` predates the merge, so neither its public-key nor its symmetric series carry version weights, and its classes stay comparable with one another.

## Decisions still open

- **Model versions.** The study recorded "Sonnet" and "Opus" without versions (its sessions used Opus 5.5 for other work). We use `anthropic/claude-sonnet-5.5` for pass 1 and `anthropic/claude-opus-5.5` for pass 2. Question for the study's authors: which versions did you use?
- **Version weights for symmetric rows.** Building same-work groups for the symmetric labels, as `data/venues/duplicate_checks.csv` does for the study's, then rerunning the author map with version weights on every class.
- **Website and white paper.** `pipeline/build_site_data.py` and `paper/generate_tables.py` list their classes by hand; adding Symmetric to them is the next step.

## How to check this work

Public-key screen identical to the baseline:

```bash
git show 172f562:pipeline/candidates.py > /tmp/candidates_orig.py
python3 -I /tmp/candidates_orig.py data/raw/eprint/eprint_oai.jsonl /tmp/cand_orig.jsonl
python3 -I pipeline/candidates.py data/raw/eprint/eprint_oai.jsonl /tmp/cand_new.jsonl
python3 - <<'E'
import json
a = {json.loads(l)["eprint_id"]: json.loads(l)["kw_hits"] for l in open("/tmp/cand_orig.jsonl")}
b = {json.loads(l)["eprint_id"]: json.loads(l)["kw_hits"] for l in open("/tmp/cand_new.jsonl")}
pk = {e: {k: v for k, v in h.items() if k != "symmetric"} for e, h in b.items()}
assert {e: h for e, h in pk.items() if h} == a
print("public-key screen identical")
E
```

Re-harvest: as in `STATUS.md` ("Raw re-harvest"), with the User-Agent above.
