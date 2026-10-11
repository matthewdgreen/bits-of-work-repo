#!/usr/bin/env python3
"""Stage 1: high-recall keyword screen over title+abstract.

Emits data/candidates.jsonl with per-class hit lists. Patterns are
deliberately broad; precision comes from the classifier stage.

Usage: candidates.py [IN] [OUT] [CLASS]. Without CLASS: the study's public-key
classes, ignoring symmetric hits. CLASS=symmetric: symmetric candidates only.
"""
import json, re, sys, collections

IN = sys.argv[1] if len(sys.argv) > 1 else "data/eprint.jsonl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "data/candidates.jsonl"
ONLY = sys.argv[3] if len(sys.argv) > 3 else None

# Each class: list of (pattern, label). A record is a candidate for a class
# if any pattern matches title or abstract (case-insensitive).
P = {
 "ecdlp": [
  (r"elliptic[- ]curve discrete log", "ecdl phrase"),
  (r"\becdlp\b", "ECDLP"),
  (r"\becdl\b", "ECDL"),
  (r"pollard'?s? (rho|kangaroo|lambda)", "pollard"),
  (r"\bkangaroo\b", "kangaroo"),
  (r"baby[- ]step giant[- ]step", "bsgs"),
  (r"summation polynomial", "semaev"),
  (r"weil descent|ghs attack|gaudry[- ]hess[- ]smart", "weil descent"),
  (r"index calculus", "index calculus"),
  (r"anomalous (elliptic )?curve|smart'?s attack|semaev.*anomalous", "anomalous"),
  (r"\bmov attack\b|menezes[- ]okamoto[- ]vanstone|frey[- ]r[uü]ck", "mov"),
  (r"generic group model.*(discrete log|lower bound)|lower bound.*generic (group|algorithm)", "generic group lb"),
  (r"koblitz curve", "koblitz"),
  (r"(solv|comput|break)\w* .{0,40}\b\d{2,3}[- ]bit .{0,40}(ecdlp|elliptic|discrete log)", "record-ish"),
  (r"interval discrete log|discrete log(arithm)? in an interval|short (exponent|interval) discrete", "interval dlp"),
  (r"(static|one-more|oracle[- ]assisted) (diffie|dh|discrete log)", "static dh"),
  (r"cheon'?s? (attack|algorithm)|discrete log(arithm)? with auxiliary input", "cheon"),
  (r"\bsecp\d{3}[rk]1\b|\bp-?256\b|curve25519|ed25519|nist curve|brainpool|sect\d{3}|ecc2k|eccp-?\d|certicom challenge", "named curve"),
  (r"shor'?s? algorithm.{0,80}(elliptic|ecc|ecdlp|curve)|(elliptic|ecc|ecdlp|curve).{0,80}shor'?s? algorithm|quantum resource.{0,80}(elliptic|ecdlp)", "shor ecc"),
  (r"discrete log.{0,600}(elliptic|curve|jacobian)|(elliptic|curve|jacobian).{0,600}discrete log", "dlog+curve"),
  (r"hyperelliptic.{0,80}(attack|index calculus|discrete log|decompos)", "hyperelliptic"),
  (r"quantum cryptanalysis|quantum (circuit|resource).{0,60}(elliptic|curve|ecc)", "quantum ecc"),
  (r"discrete log", "dlog generic"),
 ],
 "lattice": [
  (r"learning with errors|\blwe\b|\bm-?lwe\b|\br-?lwe\b|module[- ]lwe|ring[- ]lwe|\blwr\b|learning with rounding", "lwe family"),
  (r"\bntru\b", "ntru"),
  (r"\bbkz\b|block korkine|lattice (basis )?reduction|\blll\b", "reduction"),
  (r"lattice sieving|sieve.{0,30}lattice|lattice.{0,30}siev|gausssieve|\bg6k\b|tensor core", "sieving"),
  (r"lattice enumeration|enumeration.{0,30}(lattice|svp|bkz)|(svp|bkz).{0,30}enumeration|extreme pruning", "enumeration"),
  (r"shortest vector problem|\bsvp\b|closest vector problem|\bcvp\b|bounded distance decoding|\bbdd\b|unique[- ]svp|usvp", "svp/cvp"),
  (r"\bbkw\b|blum[- ]kalai[- ]wasserman", "bkw"),
  (r"arora[- ]ge", "arora-ge"),
  (r"dual attack|primal attack|hybrid attack|decoding attack.{0,40}lattice", "attack names"),
  (r"ideal lattice|ideal[- ]svp|module[- ]svp|principal ideal|unit group|cyclotomic.{0,40}(attack|short|generator|quantum)|stickelberger|log[- ]unit", "ideal structure"),
  (r"\bkyber\b|ml-kem|frodo(kem)?|saber\b|dilithium|ml-dsa|falcon\b|newhope|sntrup|ntru prime|ntru-hrss", "pqc lattice scheme"),
  (r"(svp|lwe|ideal lattice|ntru) challenge|darmstadt", "challenge"),
  (r"lattice estimator|estimate all the|security estimat\w+.{0,40}lattice|lattice.{0,40}security estimat", "estimator"),
  (r"(cryptanaly|attack|solv|break)\w*.{0,60}\blattice", "cryptanalysis+lattice"),
  (r"\blattice\b.{0,60}(cryptanaly|attack|solv|break)", "lattice+cryptanalysis"),
  (r"quantum.{0,60}(lattice|lwe|svp|ideal)|(lattice|lwe|svp|ideal).{0,60}quantum", "quantum lattice"),
 ],
 "code": [
  (r"information[- ]set decoding|\bisd\b", "isd"),
  (r"syndrome decoding|decoding problem|\bsdp\b", "sd"),
  (r"mceliece|niederreiter", "mceliece"),
  (r"goppa", "goppa"),
  (r"\bhqc\b|hamming quasi|\bbike\b|\bmdpc\b|\bldpc\b.{0,40}(crypt|attack|key)|quasi[- ]cyclic", "qc schemes"),
  (r"\bstern'?s? (algorithm|attack)|dumer|\bmmt\b|\bbjmm\b|may[- ]ozerov|both[- ]may|prange|lee[- ]brickell|canteaut[- ]chabaud", "isd names"),
  (r"low[- ]weight codeword|minimum[- ]weight codeword|codeword finding", "lwcf"),
  (r"decoding (one out of many|challenge)|\bdoom\b", "doom/challenge"),
  (r"(distinguish|structural attack|key[- ]recovery)\w*.{0,60}(goppa|code|mceliece|rank)", "structural"),
  (r"(decryption|decoding) failure.{0,60}(mdpc|bike|hqc|qc)|reaction attack|(mdpc|bike|hqc).{0,60}(decryption|decoding) failure", "dfr attacks"),
  (r"code[- ]based.{0,60}(cryptanaly|attack|security|estimat)|(cryptanaly|attack|security estimat|complexity).{0,60}code[- ]based", "code-based crypto attack"),
  (r"learning parity with noise|\blpn\b", "lpn"),
  (r"rank (metric|syndrome)|rank decoding|\bmrd\b|gabidulin|\brqc\b|\brollo\b", "rank metric"),
  (r"quantum.{0,60}(decoding|isd|code[- ]based)|(decoding|isd|code[- ]based).{0,60}quantum", "quantum isd"),
 ],
 "comparator": [
  (r"number field sieve|\bnfs\b|\bgnfs\b|\bsnfs\b|function field sieve|quadratic sieve|rsa[- ]?\d{3}\b|factor\w* .{0,30}\brsa\b|integer factori[sz]ation", "factoring/nfs"),
  (r"\bsidh\b|\bsike\b|supersingular isogeny.{0,60}(attack|break|cryptanaly)|castryck|glue[- ]and[- ]split|torsion point attack", "isogeny"),
  (r"isogen\w*.{0,80}(attack|break|cryptanaly|security of|hardness|key recovery|computing|endomorphism ring|path)|(attack|break|cryptanaly|key recovery|security of).{0,80}isogen|endomorphism ring.{0,40}supersingular|supersingular.{0,40}endomorphism ring|\bcsidh\b|\bsqisign\b|kani'?s lemma", "isogeny wide"),
  (r"(weakness|discrete log).{0,80}\bf_\{?[23]\^|finite field.{0,40}discrete log.{0,40}(record|comput|weak)|quasi-?polynomial.{0,60}discrete log", "ffdlp records"),
  (r"\brainbow\b|unbalanced oil|\buov\b|\bhfe\b|multivariate.{0,60}(attack|cryptanaly|break)|minrank|\bgemss\b", "multivariate"),
 ],
 # Symmetric class (notes/symmetric_preregistration.md). Technique names are specific to
 # symmetric cryptanalysis; primitive names count only beside an attack word.
 "symmetric": [
  (r"differential cryptanaly|linear cryptanaly|differential[- ]linear|impossible differential|truncated differential|"
   r"boomerang (attack|distinguish|connectivity)|rectangle attack|integral (attack|distinguish|cryptanaly)|square attack|"
   r"cube (attack|tester|distinguish)|rebound attack|biclique|slide attack|related[- ]key (attack|differential|boomerang|cryptanaly)|"
   r"zero[- ]correlation|division propert|correlation attack|guess[- ]and[- ]determine|"
   r"(differential|linear) (trail|characteristic|hull|propagation)|(mixed[- ]integer|milp|sat)[- ]based.{0,60}(trail|differential|linear|cryptanaly)", "symmetric technique"),
  (r"(collision|preimage|second[- ]preimage|near[- ]collision|multi[- ]?collision|length[- ]extension|herding) (attack|finding|search|resistance)"
   r"|(attack|cryptanaly)\w*.{0,60}hash function|hash function.{0,60}(attack|cryptanaly)", "hash attack"),
  (r"(cryptanaly|attack|distinguish|key[- ]recovery|break|weak key|collision|preimage|forger)\w*.{0,80}"
   r"\b(aes|rijndael|des|3des|triple[- ]des|blowfish|twofish|serpent|camellia|rc[456]|salsa20?|chacha\d*|trivium|a5/[12]|zuc|kasumi|misty\d?|"
   r"sha-?[0123]|sha-?(224|256|384|512)|keccak|shake|md[45]|ripemd|blake\d?|skein|gr(o|ø)stl|whirlpool|sm[34]|streebog|kuznyechik|gost|skinny|"
   r"prince|ascon|xoodoo|xoodyak|gimli|spongent|poseidon|mimc|haraka|even[- ]mansour|feistel|xtea|threefish|shacal|lai[- ]massey|"
   r"block cipher|stream cipher|tweakable|permutation|sponge|keystream|mac|aead|authenticated encryption|s-?box|(?-i:PRESENT|IDEA|X?TEA|GIFT|SNOW|Grain|Rescue|SIMON|Simon|SPECK|Speck|PRINCE|Midori|KATAN|ARX|Romulus|PHOTON))\b"
   r"|\b(aes|rijndael|des|3des|serpent|camellia|rc4|salsa20?|chacha\d*|trivium|a5/[12]|zuc|kasumi|sha-?[0123]|sha-?(256|512)|keccak|md[45]|ripemd|blake\d?|"
   r"skein|whirlpool|sm[34]|gost|skinny|ascon|xoodoo|gimli|poseidon|mimc|even[- ]mansour|feistel|block cipher|stream cipher|"
   r"tweakable block cipher|keyed permutation|sponge|(?-i:PRESENT|IDEA|X?TEA|GIFT|SNOW|Grain|Rescue|SIMON|Simon|SPECK|Speck|PRINCE|Midori|KATAN|ARX|Romulus|PHOTON))\b.{0,80}(cryptanaly|attack|distinguish|key[- ]recovery|weak key|collision|preimage|forger)", "primitive+attack"),
  (r"time[- ]memory(-data)? trade[- ]?off|grover.{0,60}(aes|key search|cipher|hash)|(aes|key search|cipher|hash).{0,60}grover|"
   r"quantum.{0,60}(symmetric|block cipher|even[- ]mansour|feistel|simon'?s algorithm)|simon'?s (algorithm|period)", "generic/quantum symmetric"),
 ],
}
PC = {k: [(re.compile(p, re.I | re.S), lab) for p, lab in v] for k, v in P.items()}

# Exclusion hints: not applied as hard filters, recorded for the classifier.
EXCL = re.compile(r"homomorphic|\bfhe\b|zero[- ]knowledge|\bsnark|blockchain|side[- ]channel|fault (attack|injection)|masking|hardware implementation|fpga implementation|constant[- ]time|power analysis", re.I)

counts = collections.Counter(); multi = collections.Counter()
with open(IN) as f, open(OUT, "w") as out:
    for line in f:
        r = json.loads(line)
        text = r["title"] + " \n " + r["abstract"]
        hits = {}
        for cls, pats in PC.items():
            labs = [lab for rx, lab in pats if rx.search(text)]
            if labs: hits[cls] = labs
        if not hits: continue
        # dlog generic alone is too weak to make an ECDLP candidate; symmetric hits do not rescue it
        if hits.get("ecdlp") == ["dlog generic"] and set(hits) <= {"ecdlp", "symmetric"}: del hits["ecdlp"]
        if ONLY:
            if ONLY not in hits: continue
        else: hits.pop("symmetric", None)
        if not hits: continue
        r["kw_hits"] = hits
        r["excl_hints"] = sorted(set(m.group(0).lower() for m in EXCL.finditer(text)))
        out.write(json.dumps(r, ensure_ascii=False) + "\n")
        for c in hits: counts[c] += 1
        multi[len(hits)] += 1
print("candidates per class:", dict(counts))
print("records by number of classes hit:", dict(multi))
