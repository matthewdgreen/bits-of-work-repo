#!/usr/bin/env python3
"""Label classifier batches through the OpenRouter API (symmetric extension).

Usage: OPENROUTER_API_KEY=... classify_openrouter.py PASS MODEL BATCH_DIR LABEL_DIR BUDGET_USD [WORKERS]

PASS is 1 or 2 and selects the "API pass N" instructions in pipeline/classify_prompt.md;
the system message is those instructions plus pipeline/rubric.md, the user message is
one batch_NNNN.txt. Each batch's labels go to LABEL_DIR/batch_NNNN.jsonl, written only
when every line parses and the ids equal the batch's; a rerun skips finished batches.
Each call appends one row to LABEL_DIR/usage.tsv. BUDGET_USD caps the total cost
recorded in every usage.tsv under data/symmetric/; the runner starts no call once it
is reached (calls already running may add at most WORKERS more).
"""
import glob, http.client, json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

PASS, MODEL, BATCH_DIR, LABEL_DIR, BUDGET = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
WORKERS = int(sys.argv[6]) if len(sys.argv) > 6 else 8
assert PASS in ("1", "2"), "PASS must be 1 or 2"
KEY = os.environ["OPENROUTER_API_KEY"]
os.makedirs(LABEL_DIR, exist_ok=True)

doc = open("pipeline/classify_prompt.md").read()
m = re.search(rf"### API pass {PASS}\n(.*?)(?=\n### |\Z)", doc, re.S)
assert m, f"no 'API pass {PASS}' section in pipeline/classify_prompt.md"
SYSTEM = m.group(1).strip() + "\n\n" + open("pipeline/rubric.md").read()

def spent():
    total = 0.0
    for p in glob.glob("data/symmetric/**/usage.tsv", recursive=True):
        for line in open(p):
            f = line.rstrip("\n").split("\t")
            if f[0] != "batch": total += float(f[5])
    return total

def call(messages):
    body = json.dumps({"model": MODEL, "max_tokens": 32000, "usage": {"include": True},
                       "messages": [{"role": "system", "content": SYSTEM}] + messages}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
        "X-Title": "bits-of-work symmetric extension (John Servil)"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())

def reply(messages, stem, attempt):
    """One API call; logs its usage; returns the reply's JSON lines (JSONDecodeError if one fails to parse)."""
    resp = call(messages)
    u = resp.get("usage") or {}
    with open(os.path.join(LABEL_DIR, "usage.tsv"), "a") as f:
        f.write(f"{stem}\t{resp.get('model', MODEL)}\t{attempt}\t{u.get('prompt_tokens', 0)}\t{u.get('completion_tokens', 0)}\t{u.get('cost', 0)}\n")
    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return [json.loads(l) for l in content.splitlines() if l.strip().startswith("{")]

def label(path):
    stem = os.path.basename(path)[:-4]
    out = os.path.join(LABEL_DIR, stem + ".jsonl")
    if os.path.exists(out): return f"{stem}: done earlier"
    text = open(path).read()
    ids = re.findall(r"^### (.+)$", text, re.M)
    for attempt in range(4):
        if spent() >= BUDGET: return f"{stem}: budget ${BUDGET:.2f} reached, not sent"
        try:
            rows = reply([{"role": "user", "content": text}], stem, attempt)
            got = [r.get("id") for r in rows]
            missing = [i for i in ids if i not in got]
            if missing and set(got) <= set(ids):  # the subagents' self-check: ask once for the missing lines
                rows += reply([{"role": "user", "content": text}, {"role": "assistant", "content": "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)},
                               {"role": "user", "content": "Your reply lacks labels for these ids: " + ", ".join(missing) + ". Reply with exactly those JSON lines and nothing else."}],
                              stem, attempt)
                got = [r.get("id") for r in rows]
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError) as e:
            time.sleep(10 * 2 ** attempt); err = repr(e)[:200]; continue
        except json.JSONDecodeError as e: err = f"unparsable line: {e}"; continue
        if sorted(got) != sorted(ids):
            err = f"ids differ: {len(set(ids) - set(got))} missing, {len(set(got) - set(ids))} unknown, {len(got)} lines"; continue
        tmp = out + ".tmp"
        with open(tmp, "w") as f:
            for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, out)
        return f"{stem}: {len(rows)} labeled"
    return f"{stem}: FAILED after 4 attempts ({err})"

usage = os.path.join(LABEL_DIR, "usage.tsv")
if not os.path.exists(usage):
    open(usage, "w").write("batch\tmodel\tattempt\tprompt_tokens\tcompletion_tokens\tcost_usd\n")
batches = sorted(glob.glob(os.path.join(BATCH_DIR, "batch_*.txt")))
print(f"pass {PASS}, {MODEL}: {len(batches)} batches; spent so far ${spent():.2f} of ${BUDGET:.2f}", flush=True)
with ThreadPoolExecutor(WORKERS) as ex:
    for msg in ex.map(label, batches): print(msg, flush=True)
print(f"spent ${spent():.2f} of ${BUDGET:.2f}")
