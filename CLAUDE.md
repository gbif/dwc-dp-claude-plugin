# CLAUDE.md

Rules for everyone working on this repository, including cloud agents running from GitHub issues.

## What this is

A Claude Code plugin (`skills/dwc-dp/`) that guides biologists from their own files to a valid
Darwin Core Data Package (DwC-DP) 1.0, and `dwcdp.py`, the DuckDB tool it uses. Data holders
rarely know relational modelling, so the plugin explains it with their own records and lets them
decide.

## Sources of truth, in this order

1. The vendored DwC-DP 1.0 table schemas and profile in `skills/dwc-dp/schemas/1.0/`: which
   tables and fields exist, the keys, the predicates, and the constraints.
2. The DwC-DP guide, https://dwc.tdwg.org/dp/. Section 3 is normative. Its example in section 2
   still uses `eventID` as the key, from before 1.0; the schemas win.
3. The Darwin Core conceptual model, https://dwc.tdwg.org/cm/. It is non-normative, so use it to
   explain, not to require.
4. Examples, as patterns only: https://github.com/gbif/dwc-dp-examples (Apache-2.0, written before
   1.0, mostly natural keys) and https://github.com/gbif/model-material (no licence: read it, never
   copy from it). Never take a field name or rule from an example.

Also:

- **GBIF vocabularies:** https://api.gbif.org/v1/vocabularies, pinned in
  `skills/dwc-dp/vocabularies/`. Which field uses which vocabulary is GBIF's configuration
  (gbif/pipelines `pipelines.yaml`, `vocabularyConfig`), never a guess.
- **GBIF's DwC-DP validator:** https://github.com/gbif/dwc-dp-analyser, what GBIF runs on crawled
  packages. `check` should agree with it.
- **GBIF's DwC-DP crawling:** https://github.com/gbif/crawler (`dwcdp` packages).
- **The IPT's DwC-DP work:** the `dwc-dp` branch of https://github.com/gbif/ipt.

The plugin's goal is a valid package. Publishing is out of scope.

## Never guess

When the sources above don't settle a question (what a field means, which table a kind of data
belongs in, which vocabulary is meant, what the data holder or maintainer wants), stop:

- on an issue, post the question with what you found and where (file and field, or URL and
  section), the options you see, and what each would mean;
- add the `needs-human` label, remove `in-progress`, and end the run.

Don't write "probably", "likely" or "assuming" into code, docs or recipes. An open question is
written as an open question.

Every claim about the standard in an issue, PR, recipe or doc cites its source: a schema file and
field, or a URL and section.

## Working on issues

- **One issue per branch and PR.** The branch is named `issue-<n>-<short-name>`, and the PR says
  `closes #<n>`.
- **Before opening a PR,** run `python3 -m unittest discover tests` and say in the PR what you ran
  and its result. A change to `dwcdp.py` comes with a test.
- **Merging is for the maintainer only.** Never approve or merge a PR.
- **Never push to `main`.**
- **New issues you file are labelled `proposed`.** The exception is an issue that splits up one
  already labelled `ready`: it may be `ready` too, and it links its parent.
- **Labels:**
  - `ready`: may be taken;
  - `in-progress`: taken;
  - `needs-human`: waiting for the maintainer;
  - `proposed`: waiting for the maintainer to accept;
  - kind: `survey`, `edna`, `specimens`, `observations`;
  - type: `tooling`, `recipe`, `docs`.

## Never

- Edit the vendored schemas or vocabularies. Move to a new pin only with `tools/pin_schemas.py` or
  `tools/pin_vocabularies.py`, in its own PR.
- Commit data without a clear open licence, or any data from `gbif/model-material`. Fixtures are
  small, synthetic or cut from Apache-2.0 sources, with the source named in the fixture's README.
- Contact anyone outside this repository, or open issues or PRs in other repositories.
- Add dependencies beyond the Python standard library and `duckdb`.

## Writing

- **Commit messages, issues and PRs:**
  - one short lower-case subject line, such as `check foreign keys in check`;
  - no "Summary", "Changes" or "Test plan" headings, and no generated bullet lists;
  - no Co-Authored-By or other attribution lines.
  - A body only for a reason or decision the diff can't show.
- **Plugin text (SKILL.md and references):** plain words for biologists. Explain a term once, and
  use the data holder's records as examples.
- **Plugin version:** bump `.claude-plugin/plugin.json` in every PR that changes anything under
  `skills/`. Installs are cached by version, so a change without a bump never reaches anyone.

## Layout

- `skills/dwc-dp/SKILL.md`: the workflow and rules for Claude.
- `skills/dwc-dp/references/`:
  - `concepts.md`, `choosing-tables.md`, `interactions.md` and `assertions.md`;
  - `package.md`;
  - `recipes/`, one file per kind of dataset (see `recipes/README.md`).
- `skills/dwc-dp/scripts/dwcdp.py`: the CLI, with these commands:
  - `tables`, `describe`, `find-term`, `order` and `vocab` read the schemas and vocabularies;
  - `init`, `load`, `load-dwca`, `suggest`, `run`, `sql`, `status`, `validate`, `diagram`,
    `metadata-template`, `package` and `summary` work on the working DuckDB;
  - `check` tests a package on disk;
  - `grscicoll` looks institution and collection codes up in GBIF's GRSciColl API. It is the
    tool's only network call, and its tests use recorded responses on a local server.
- `tests/`: `unittest`, with fixtures in `tests/fixtures/`.
- `skills/dwc-dp/vocabularies/`: the pinned GBIF vocabularies and `mapping.json`.
- `tools/pin_schemas.py` and `tools/pin_vocabularies.py`: copy the schemas from a tdwg/dwc commit,
  and the GBIF vocabularies.
- `BACKLOG.md`: planned work, until it becomes GitHub issues.
