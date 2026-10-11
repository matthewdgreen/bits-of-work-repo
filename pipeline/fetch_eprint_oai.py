#!/usr/bin/env python3
"""Harvest the full Cryptology ePrint Archive via OAI-PMH (oai_dc).

Writes one XML file per page to data/raw/eprint/page_NNNN.xml and a
resume file so an interrupted run can continue. Polite: 1.5 s between
requests, retries with backoff.
"""
import os, re, sys, time, urllib.request, urllib.parse, urllib.error

BASE = "https://eprint.iacr.org/oai"
OUT = sys.argv[1] if len(sys.argv) > 1 else "data/raw/eprint"
os.makedirs(OUT, exist_ok=True)
STATE = os.path.join(OUT, "resume.token")
UA = "bits-of-work-symmetric-extension/0.1 (John Servil; mailto:johnservil@proton.me; https://github.com/johnservil)"

def get(url, tries=6):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            wait = 5 * (2 ** i)
            print(f"retry {i+1} after error {e!r}; sleeping {wait}s", flush=True)
            time.sleep(wait)
    raise SystemExit("giving up")

token = None
page = 0
if os.path.exists(STATE):
    token, page = open(STATE).read().strip().split("\t")
    page = int(page)
    print(f"resuming at page {page} with token {token}", flush=True)

while True:
    if token is None:
        url = f"{BASE}?verb=ListRecords&metadataPrefix=oai_dc"
    else:
        url = f"{BASE}?verb=ListRecords&resumptionToken={urllib.parse.quote(token)}"
    body = get(url)
    if "<error" in body[:2000]:
        print(body[:2000]); raise SystemExit("OAI error")
    with open(os.path.join(OUT, f"page_{page:04d}.xml"), "w") as f:
        f.write(body)
    n = body.count("<record>")
    m = re.search(r'<resumptionToken[^>]*>([^<]*)</resumptionToken>', body)
    cursor = re.search(r'cursor="(\d+)"', body)
    print(f"page {page}: {n} records, cursor={cursor.group(1) if cursor else '?'}", flush=True)
    page += 1
    if not m or not m.group(1).strip():
        break
    token = m.group(1).strip()
    with open(STATE, "w") as f:
        f.write(f"{token}\t{page}")
    time.sleep(1.5)

if os.path.exists(STATE):
    os.remove(STATE)
print("done", flush=True)
