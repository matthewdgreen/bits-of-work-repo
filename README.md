# Bits of Work: measuring public cryptanalytic effort

An AI-conducted analysis, overseen by Matthew Green. Website: <https://bitsofwork.org>.

This study estimates how much public cryptanalysis each public-key hardness assumption has received
(ECDLP, structured and plain lattices, syndrome decoding; factoring/FF-DLP, isogenies and multivariate
as comparators), from the literature itself. It counts classified attack papers, maps authors to
publication-based research-allocation years, tracks computational records and the gap between the
largest public solve and deployed parameters, and expresses historical effort as AI inference-budget
scenarios. All results are provisional and mostly not yet human-validated.

## What is here

- `SUMMARY.md`: findings in one page. `PLAN.md`: methodology. `STATUS.md`: state of the work.
- `pipeline/`: harvesters (IACR ePrint OAI-PMH, DBLP, OpenAlex, zbMATH), keyword screen,
  classification rubric (`pipeline/rubric.md`), merge, author-map and export scripts. Python 3 stdlib.
- `analysis/`: reports, counts and the scripts that produce them.
- `data/`: candidate pools, two-pass classifier labels, the combined export of included items,
  aggregate research-allocation series (`data/authors/fte_by_year.csv`) and AI-effort calibration data.
- `records/`: computational records (one YAML file per record, with sources).
- `paper/`, `output/pdf/`: the working white paper. `docs/`: the website.
- `notes/symmetric_extension.md`: an extension adding a symmetric-cryptanalysis class, with every
  change it makes to the study's code, data and method. Definitions: `notes/symmetric_preregistration.md`.

## What was removed from this public copy

This repository is exported from a private working repository by `pipeline/export_public.py`.
The export removes material that is copyrighted by others or that profiles individuals:

- **Abstracts.** Third-party abstracts are stripped from every data file, and the classifier input
  batches (which embed titles and abstracts) are omitted. Titles, identifiers (ePrint ids, DOIs,
  OpenAlex/DBLP/zbMATH keys), labels and the classifier's own one-line reasons are kept, so
  abstracts can be re-fetched from the original sources.
- **Full texts.** Copies of papers and specifications assembled for the HAWK rediscovery pilot are omitted;
  `data/ai_effort/pilot_hawk/packet_notes.md` lists what the packet contained.
- **Person-level author data.** Per-person tables (career-stage estimates, employment sector,
  per-person effort shares) and per-person ranking lists are omitted. Aggregate series by class and
  year are kept. Paper author lists remain as ordinary bibliographic metadata.

Scripts that need the removed inputs (for example the author-map rebuild) will not run from this copy
without re-harvesting; the raw-harvest commands are in `STATUS.md`.

## Data sources

IACR Cryptology ePrint Archive; dblp computer science bibliography (CC0); OpenAlex (CC0);
zbMATH Open (CC BY-SA 4.0; derived zbMATH metadata in this repository is shared under the same terms).
