# Classification rubric (Phase 1, v0.4)

You are labeling cryptography papers for a bibliometric study of public
cryptanalytic effort against the assumptions behind standardized public-key
encryption, and (v0.4) against symmetric primitives. You see only title,
authors, year, ePrint category and abstract.
Judge what the paper DOES, not what it mentions.

## include

- `yes`: the paper's main contribution is cryptanalytic work on one of the
  problems below (categories A-F, H) or hardness theory about them (G), or
  it is a survey/thesis centred on attacks on them (S).
- `no`: the paper merely USES the assumption (constructions, protocols, FHE,
  ZK, signatures), or is about implementation, side channels, fault attacks,
  hardware, masking, formal verification, or attacks on protocol/scheme
  details that say nothing about the underlying problem.
- (v0.3.3) Unvetted claims of polynomial-time (or otherwise sensational) attacks on
  factoring/DLP/LWE/SD with no credible analysis, typically from non-reviewed outlets
  (viXra etc.), are include=no, category X, reason starting "unvetted claim". Category H
  is only for serious attacks later withdrawn or refuted.
- `borderline`: genuinely unclear from the abstract, or scheme-level attack
  that might bear on the problem (e.g. decryption-failure attacks on
  QC-MDPC/HQC, invalid-ciphertext attacks whose core is a decoding step).

## category (one)

- A  classical algorithm for the problem, new or improved (incl. asymptotics,
     time-memory trade-offs, new implementations whose point is speed).
- B  quantum algorithm or quantum resource estimate for the problem.
- C  structural result: exploits or rules out special structure (Weil
     descent, anomalous/pairing-friendly curves, ideal/module/cyclotomic
     structure, Goppa/QC structure, distinguishers, weak keys).
- D  concrete cost model / security estimate / parameter-selection analysis
     (estimators, cost of BKZ/ISD/rho in bits, "is Kyber-512 128-bit").
- E  computational record: actually solves a concrete instance (challenge
     entry, record computation) and reports resources.
- F  negative or generic-model result: lower bounds, impossibility of a
     class of attacks.
- G  hardness theory: reductions between variants, worst-case/average-case,
     equivalence results. No attack.
- H  claimed attack later retracted/withdrawn, or paper whose main point is
     to refute a claimed attack.
- S  survey, SoK, tutorial or thesis centred on attacks.
- X  not relevant (use with include=no).

## problem_tags (one or more, each with a weight in (0,1], weights sum to 1)

Tag the PROBLEM the technique actually addresses, not the schemes named as
motivation. If a technique is generic to a family, use the generic tag and
let downstream attribution split it.

- `ecdlp`              DLP on elliptic curves, any field; EC-CDH/DDH/gap/static
                       DH; interval ECDLP; Shor-on-EC.
                       (v0.3.2) Includes DLP in Jacobians of hyperelliptic and
                       other low-genus curves (index calculus, Weil-descent targets):
                       tag ecdlp, include yes when it is an algorithm/attack.
- `ffdlp`              DLP in finite fields (index calculus, NFS/FFS) — only
                       when curves are not a target.
- `factoring`          integer factoring.
- `lattice_generic`    SVP/CVP/BDD/uSVP, BKZ, sieving, enumeration, dual/primal
                       attack machinery applying to all lattice assumptions.
                       (v0.3.4) New or faster lattice-reduction algorithms (LLL
                       variants, floating-point/segment/parallel LLL, BKZ variants)
                       are yes, A, layer 0, even without a stated crypto target;
                       pure average-case analyses of reduction algorithms are yes, A
                       or F. Lattice reduction applied to MIMO/signal processing is no.
- `lwe_plain`          attacks or estimates specific to unstructured LWE/LWR
                       (BKW, Arora-Ge, small-secret, Frodo parameter work).
- `lattice_structured` ideal/module/cyclotomic structure: ideal-SVP, unit
                       group, principal ideal, Ring/Module-LWE-specific
                       attacks or non-attacks, ML-KEM/Kyber-specific estimates.
- `ntru`               NTRU problem specifically (hybrid attacks, overstretched
                       NTRU, NTRU Prime, sntrup).
- `sis`                SIS/MSIS/RSIS-specific (signature side; keep for layer-0
                       sharing analysis).
- `sd_generic`         syndrome decoding / ISD / low-weight codeword finding,
                       Hamming metric, generic codes.
- `sd_goppa`           Goppa / Classic McEliece structure: distinguishers,
                       structural key recovery, McEliece parameter estimates.
- `sd_qc`              quasi-cyclic / MDPC / HQC / BIKE: DOOM, QC structure,
                       decryption-failure (reaction) attacks.
- `lpn`                learning parity with noise.
- `rank`               rank-metric decoding (RQC, ROLLO, Gabidulin attacks).
- `isogeny`            SIDH/SIKE/CSIDH cryptanalysis.
                       (v0.3.1) Attacks or quantum-cost analyses of CSIDH itself count;
                       abstract group-action problems with no isogeny content are out of
                       scope (no) or at most borderline.
- `multivariate`       MQ/UOV/Rainbow/HFE/MinRank cryptanalysis.
- `symmetric`          (v0.4) cryptanalysis of symmetric primitives: block ciphers,
                       stream ciphers, hash functions and compression functions,
                       MACs, permutations, AEAD primitives. Counts (include yes):
                       full- or reduced-round attacks, distinguishers, collisions,
                       preimages, related-key and key-recovery attacks (A, or C when
                       they exploit special structure such as weak keys or invariant
                       subspaces); generic attacks on primitives and on modes or
                       constructions as such (time-memory trade-offs, birthday and
                       multi-target attacks, generic hash-mode attacks) (A); quantum
                       attacks and resource estimates, e.g. Grover, Simon (B); cost
                       estimates and automated search for trails and attacks (A or D);
                       record computations with stated resources (E); bounds ruling out
                       a class of attacks, e.g. trail-probability bounds (F); withdrawn
                       attacks (H). Security proofs for modes and constructions
                       (indifferentiability, PRP/PRF bounds) are yes, G. Every
                       primitive counts: standards, competition candidates, lightweight,
                       arithmetization-oriented, classical, chaos-based and amateur
                       designs. Stays include=no: side channels, faults,
                       implementation; design papers, including their own security
                       sections; attacks that depend on how an application or protocol
                       uses a mode (padding oracles, protocol-level misuse). Hash
                       functions built on public-key problems take their public-key tag.
- `rsa_variant`        Coppersmith-style / small-exponent / partial-key attacks on
                       structured RSA (not generic factoring). Use instead of
                       `factoring` for these.
- `other`              anything else (then include is almost always no).
                       Explicitly OUT of scope (include=no, tag other): permuted
                       kernel (PKP), code equivalence (LESS), lattice isomorphism
                       (HAWK/LIP), hidden subset sum, group-action/CSIDH-only
                       problems.

## other fields

- `layer`: 0 generic machinery; 1 assumption-specific structure; 2 analysis
  aimed at concrete deployed/standardized parameter sets (name them in
  `params` if given: e.g. Kyber-512, P-256, secp256k1, mceliece348864,
  HQC-128, FrodoKEM-640, BIKE-L1, sntrup761).
- `regime`: for lattice items only: `pqc` (ML-KEM-like: small n, q<2^16,
  ternary/binomial noise), `fhe` (huge q, tiny secret, FHE parameters),
  `both`, or `na`.
- `leakage`: true iff the paper studies the problem given abstract hints or
  partial information on the instance (e.g. "LWE with side information",
  "NTRU with hints", decoding with known positions). Such papers are
  include=yes (category D or C) because they quantify hardness under leakage.
  Papers whose contribution is EXTRACTING leakage from an implementation
  (power, timing, cold boot, faults) remain include=no.
- `is_record`: true iff the paper reports solving a concrete instance with
  stated resources (hardware, time).
- `regime`: must be set for every lattice item, not only reviewed ones.
- `quantum`: true iff quantum algorithms/resources are the main point.
- `confidence`: 0.0-1.0 in your include+category judgement.
- `reason`: at most 20 words.

## output

One JSON object per input item, one per line, exactly these keys:
{"id", "include", "category", "problem_tags": {tag: weight, ...},
 "layer", "params": [..], "regime", "leakage", "is_record", "quantum",
 "confidence", "reason"}   (use the item's id exactly as given in the "### " header)

Do not skip items. Do not add commentary outside the JSON lines.

## calibration examples

- "Faster sieving for shortest lattice vectors using spherical LSH" ->
  include yes, A, {lattice_generic:1}, layer 0, regime na.
- "On the concrete hardness of Learning with Errors" (estimator paper) ->
  yes, D, {lattice_generic:0.6, lwe_plain:0.4}, layer 0, regime both.
- "Report on the security of LWE: improved dual lattice attack" (MATZOV) ->
  yes, D, {lattice_generic:0.5, lattice_structured:0.5}, layer 2,
  params [Kyber-512], regime pqc.
- "Soliloquy: a cautionary tale" -> yes, C, {lattice_structured:1}, layer 1.
- "McEliece needs a break: solving McEliece-1284 and QC-3138" -> yes, E,
  {sd_generic:0.5, sd_goppa:0.3, sd_qc:0.2}, layer 0, is_record true.
- "A key recovery attack on MDPC with CCA security using decoding errors"
  -> borderline, C, {sd_qc:1}, layer 1 (scheme-level, decoding failures).
- "Solving a 112-bit prime elliptic curve discrete logarithm problem on
  game consoles" -> yes, E, {ecdlp:1}, layer 0, is_record true.
- "Summation polynomial algorithms for elliptic curves in characteristic
  two" -> yes, A, {ecdlp:1}, layer 1.
- "Fully homomorphic encryption from Ring-LWE" -> no, X.
- "Kyber: a CCA-secure module-lattice-based KEM" -> no, X (construction;
  its security analysis chapter is not a separate cryptanalysis paper).
- "Masked implementation of Kyber" -> no, X.
- "Quantum algorithms for lattice problems" (Chen 2024, withdrawn) -> yes,
  H, {lattice_generic:1}, quantum true.
- "A one-more discrete log assumption is hard in the generic group model"
  -> yes, F, {ecdlp:0.5, ffdlp:0.5}, layer 0.
- "Factoring RSA-250" -> yes, E, {factoring:1}, is_record true.
- (v0.4) "Finding collisions in the full SHA-1" -> yes, A, {symmetric:1},
  layer 2, params [SHA-1].
- (v0.4) "The first collision for full SHA-1" -> yes, E, {symmetric:1},
  layer 2, params [SHA-1], is_record true.
- (v0.4) "Improved differential-linear attacks on ChaCha" -> yes, A,
  {symmetric:1}, layer 2, params [ChaCha20].
- (v0.4) "MILP-based automatic search for differential trails" -> yes, A,
  {symmetric:1}, layer 0.
- (v0.4) "Quantum circuits for AES and the cost of Grover key search" -> yes,
  B, {symmetric:1}, layer 2, params [AES-128], quantum true.
- (v0.4) "Cryptanalysis of a chaos-based image encryption scheme" -> yes, A,
  {symmetric:1}, layer 1.
- (v0.4) "On the indifferentiability of the sponge construction" -> yes, G,
  {symmetric:1}, layer 0.
- (v0.4) "Ascon: submission to the NIST lightweight competition" -> no, X
  (design).
- (v0.4) "Differential fault analysis of AES" -> no, X.
- (v0.4) "Lucky Thirteen: breaking the TLS and DTLS record protocols" -> no, X
  (protocol-level use of a mode).
