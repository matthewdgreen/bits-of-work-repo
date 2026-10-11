# Symmetric cryptanalysis class: definitions fixed before measurement

Written 2026-10-10, before any symmetric candidate was screened, labeled, or counted, and before reading any symmetric estimate by Matthew Green. The git commit that adds this file dates it. Later changes go in a dated section at the end, each with its reason.

## Question

How much public cryptanalytic effort has gone into symmetric primitives, measured exactly as this study measures the public-key classes? The headline is one number: cumulative research-allocation years through 2026 (the measure behind "about 1,036 for lattices"), with fractional paper counts by era beside it.

## The class

One class, **Symmetric**, with no subclasses. The data are sparse and the method coarse, so the class stays as large-grained as the question.

**In** (include = yes), in the study's categories:

- Attacks on block ciphers, stream ciphers, hash functions and their compression functions, MACs, permutations, and AEAD primitives: full-round or reduced-round, key recovery, distinguishers, collisions, preimages, related-key (A, C, E).
- Generic attacks on primitives and on modes and constructions as such: time-memory trade-offs, birthday and multi-target attacks, generic attacks on hash modes (A).
- Quantum attacks and quantum resource estimates (B).
- Cost estimates and automated search for trails and attacks (A or D).
- Bounds that rule out a class of attacks, such as bounds on differential or linear trail probabilities (F).
- Withdrawn attacks and refutations (H).
- Every primitive counts, from standards to competition candidates, lightweight ciphers, arithmetization-oriented primitives, classical ciphers, and amateur designs, as every proposed public-key scheme counts in its class.

**Reported alongside, outside the headline:** security proofs for modes and constructions, which are the counterpart of hardness theory (G), and surveys and theses (S).

**Out** (include = no): side channels, faults, and implementation; design papers, including their own security sections (the study's rule for Kyber's specification); attacks that depend on how an application or protocol uses a mode (padding oracles, misuse); and hash functions built on public-key problems, whose attacks stay in their public-key class.

**Shared work:** a paper bearing on both a public-key class and Symmetric (for example, Gröbner-basis solving applied to multivariate schemes and to ciphers) splits its tag weights, as every other paper in the study does.

## Method, unchanged from the study

- Sources: ePrint, the DBLP dump (title screen plus venue allowlist, with FSE added), OpenAlex phrase searches, zbMATH, and one snowball round.
- Classifier: the study's two-pass protocol and models, pass 2 shown the pass-1 label, with a 10% audit of exclusions.
- Attribution: tag `symmetric`, weight 1.0 to Symmetric.
- Counts: include = yes, categories A–F and H; vetted view (ePrint plus DBLP-indexed) beside all sources.
- Research-allocation years: `analysis/author_map.py`, unchanged.

## Boundaries most likely to move the number

Any gap between this estimate and another will most likely trace to one of these; each result names its choice on each:

1. Design papers with security sections (out).
2. Cryptanalysis of chaos-based and amateur ciphers (in; the vetted view shows its weight).
3. Security proofs for modes and constructions (alongside, outside the headline).
4. Hash functions (in).

## Comparison with an independent estimate

We read Matthew Green's symmetric estimate only after our result is committed. Results within a factor of 2 in research-allocation years count as agreement. The two share the method's common assumptions (papers as the unit of effort, the allocation model), so their agreement checks the boundaries and the labeling; it leaves those shared assumptions untested.
