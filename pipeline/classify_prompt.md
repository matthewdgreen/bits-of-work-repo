# Classifier subagent prompts (Phase 1)

Recorded so runs are reproducible. `{...}` are filled per agent.
Pass 1 uses the fast model (sonnet), pass 2 the stronger model (opus).
Each agent gets a private scratch directory and an explicit list of batches.

## Pass 1

You are labeling cryptography papers for a bibliometric study. Repo:
/Users/mgreen/src/literature-search.

1. Read pipeline/rubric.md completely. It is the only labeling standard.
2. For each batch file listed below, read it from {BATCH_DIR}/ and write
   {LABEL_DIR}/<same stem>.jsonl containing exactly one JSON object per
   `### <id>` item, in the rubric's output format, with "id" copied exactly
   from the header. No other text in the file.
3. Items come from DBLP, OpenAlex, zbMATH and arXiv as well as ePrint. Some
   have no abstract; judge from title and venue, and use `borderline` with
   low confidence when the title alone cannot decide between a cryptanalytic
   and a constructive paper. Non-cryptographic papers (pure coding theory
   with no decoding-hardness angle, lattice papers in physics/chemistry,
   "lattice" in the order-theory sense, elliptic curves in pure arithmetic
   geometry with no DLP angle, chaos-based image encryption) are include=no.
4. After writing each file, check that the number of JSON lines equals the
   number of `### ` headers in the batch (e.g. with grep -c) and that every
   line parses (python3 -I -c "import json,sys;[json.loads(l) for l in open(sys.argv[1])]" FILE).
   Fix and rewrite if not.
5. Use only {SCRATCH} for any helper files. Do not modify anything else.

Batches: {LIST}

Reply with one line per batch: stem, item count, counts of yes/borderline/no.

## Pass 2

As pass 1, but batches come from make_pass2.py and each item shows a
`PASS1:` line. Treat it as a suggestion from a weaker model only; decide
independently from the rubric. Output the same JSON format (no "agree"
field needed; agreement is computed by merge_pass2.py).

## API runner (symmetric extension, rubric v0.4)

`pipeline/classify_openrouter.py` sends each batch in one API call. The
system message is the section below for the pass, followed by the full text
of pipeline/rubric.md; the user message is the batch file. It replaces the
subagent's file reading and self-checks with the runner's own: every line
must parse, and the ids must equal the batch's ids. When a reply lacks some
ids, the runner asks once, in the same conversation: "Your reply lacks labels
for these ids: <ids>. Reply with exactly those JSON lines and nothing else."
Any other mismatch, or a mismatch left after that, retries the call.

### API pass 1

You are labeling cryptography papers for a bibliometric study. The rubric
below is the only labeling standard. The user message holds one batch: each
item starts with a `### <id>` header. Items come from ePrint, DBLP, OpenAlex,
zbMATH and arXiv. Some have no abstract; judge from title and venue, and use
`borderline` with low confidence when the title alone cannot decide between
a cryptanalytic and a constructive paper. Non-cryptographic papers (pure
coding theory with no decoding-hardness angle, lattice papers in
physics/chemistry, "lattice" in the order-theory sense, elliptic curves in
pure arithmetic geometry with no DLP angle) are include=no. Reply with
exactly one JSON object per item, one per line, in the rubric's output
format, with "id" copied exactly from the header, and nothing else.

### API pass 2

As pass 1, but each item also shows a `PASS1:` line. Treat it as a suggestion
from a weaker model only; decide independently from the rubric. Output the
same JSON format.
