# Backlog

These become GitHub issues, with the labels shown, once the repository is on GitHub. Until then
they are worked on locally from this file.

## Done in the first version

- DwC-DP 1.0 schemas vendored from tdwg/dwc `95d6bbb`, with `tools/pin_schemas.py`.
- `dwcdp.py` commands:
  - `tables`, `describe`, `find-term` and `order`;
  - `init`, `load`, `run`, `sql` and `status`;
  - `validate`, `diagram`, `package` and `check`.
- SKILL.md with seven stages, `concepts.md`, `choosing-tables.md` and `package.md`.
- Tests on synthetic fixtures. No example package in gbif/dwc-dp-examples is DwC-DP 1.0, so none
  is used as a fixture.

## Ready

- **Recipe: surveys** `ready` `recipe` `survey`
  - Learn from `survey/NEON-fish`, `survey/broke-west-fish` and `survey/insektmobilen` in
    gbif/dwc-dp-examples (pre-1.0: insektmobilen has `_pk`/`_fk` columns, but its file names and
    some fields are not 1.0).
  - Write `recipes/survey.md` and a small synthetic fixture with an event hierarchy, a survey,
    survey targets and absences, and test that it validates and packages.
- **Recipe: specimens and collections** `ready` `recipe` `specimens`
  - Sources: `material/bgbm`, `material/dissco` and `material/cyanolichens`.
  - Cover material derived from material, identifications with history, agents in roles, and
    media.
- **Recipe: observations, interactions and camera traps** `ready` `recipe` `observations`
  - Sources: `observation/bird-tracking`, `organism_interaction/inaturalist` and
    `organism_interaction/conabio-bees`.
  - For camera traps, compare Camtrap DP (https://camtrap-dp.tdwg.org) deployments, media and
    observations with the DwC-DP tables, and list where they don't match as questions.
- **Recipe: eDNA** `ready` `recipe` `edna`
  - Source: `edna/obis-edna-expeditions` (0.1).
  - Covers OTU/ASV tables and sample sheets, with nucleotide-analysis, nucleotide-sequence,
    molecular-protocol and material.
- **Recipe: Darwin Core Archives** `ready` `recipe`
  - `load-dwca` stages an archive. The recipe covers the usual cores (Occurrence, Event) and
    extensions (MeasurementOrFact, Multimedia, DNA derived data, ResourceRelationship), and which
    DwC-DP tables their terms go to.
  - DwC-DP 1.0 has no table for a checklist of taxa (`identification-taxon` holds the taxon of an
    identification), so whether a Taxon core archive can be translated is a question for the
    maintainer.
  - It also covers where a flat core row splits into several tables.
  - Uses a synthetic archive fixture; cite the Darwin Core text guide (https://dwc.tdwg.org/text/)
    for meta.xml.
- **Make `check` agree with GBIF's DwC-DP analyser** `tooling` (mostly done)
  - Done, from the 0.0.16 source:
    - `check` makes the analyser's descriptor checks at its default severities: profile, `name`,
      paths, field types, duplicates, required fields, field descriptors and relationships
      (including weak ones);
    - it makes the EML checks that need no XSD, and the data checks (keys, links and types cast
      to the declared type);
    - the `--json` report names the analyser's violation type for each finding;
    - `package --name`;
    - tests for each rule (`AlignedWithAnalyser`);
    - the differences are documented in `references/package.md`.
  - Confirmed on 2026-11-23: the maintainer ran 0.0.16 on the 18 packages of
    `tests/analyser_packages.py`, which exercise every analyser rule except the
    profile-unavailable ones. `check` matches on all 18, apart from two deliberate differences in
    `references/package.md`.
    - The reports are in `tests/fixtures/analyser-0.0.16/`, and `AnalyserReports` compares against
      them.
    - The comparison found one gap, the Data Package path pattern, which is now checked.
  - Left: EML 2.2.0 XSD validation, which needs the XSD and a validator outside the standard
    library, so it stays the analyser's.
- **Keep `check` aligned in CI** `ready` `tooling`
  - In `test.yml`:
    - download the pinned analyser release jar (0.0.16), and verify it against the release's
      `checksums.txt`;
    - run it on every package the tests build, including deliberately broken ones;
    - fail when its verdict, or its list of errors, differs from `check`'s.
  - This is what lets the analyser stay optional for data holders. Moving to a new analyser
    release is its own PR, and the CI result shows what changed.
- **Optional: run the analyser locally** `ready` `tooling`
  - `dwcdp.py analyse <folder>`, for data holders who have it installed:
    - finds `dwc-dp-analyser` on the PATH, or `java -jar $DWC_DP_ANALYSER_JAR`;
    - runs it with `--output-format JSON --report VERIFY`;
    - reads `isValid`, `result.descriptorValidation.issues[]` and
      `result.resourceAnalysisResults[]` (foreign key, primary key and type violations);
    - says each in plain words.
  - Never download or install it on their behalf. If it isn't there, say `check` covers the same
    checks, and how to install it (release jar plus Java 17+, `.deb`, `.rpm`, Arch, Windows zip,
    or the Homebrew tap) if they want to.
  - It fetches the DwC-DP 1.0 schemas from rs.tdwg.org, and sends no data. Say so first.
  - Tests use a recorded JSON report as a fixture, so they run without Java.
- **Later: GBIF's validator REST service** `proposed` `tooling`
  - The analyser will become available through GBIF's validator REST service. When it is, offer
    it as a final check.
  - That sends the package to GBIF, so only on the data holder's explicit word, each time.
  - Wait until the service and its API are published; nothing to build before then.
- **Second opinion: kueda/dwc-dp-validate** `proposed` `tooling`
  - An Apache-2.0 CLI by another author. Compare once, and note differences as questions.
- **`validate`: event and material hierarchies** `ready` `tooling`
  - Detect cycles in `parentEvent_fk`, `derivedFromMaterialEntity_fk`, `isPartOfMaterialEntity_fk`
    and other self-references, and report them in plain words.
- **`check`: compressed packages and tables** `ready` `tooling`
  - Read `.gz` tables and a gzipped package (guide section 3), with tests.
- **`load`: spreadsheets without the excel extension** `ready` `tooling`
  - Reading `.xlsx` needs DuckDB's excel extension, which downloads on first use.
  - Find out whether it can be bundled or installed once, and otherwise document saving sheets as
    CSV.

## Decided

- **The goal is a valid package.** The plugin stops when `check` passes; publishing is not part
  of it.
- **Upstream examples:** don't raise their pre-1.0 state in gbif/dwc-dp-examples or tdwg/dwc.
- **eDNA:** no referral to the MDT; the plugin builds DwC-DP for eDNA as for any other data.
- **Darwin Core Archives:** yes, help translate them to DwC-DP (`load-dwca`, and the recipe above).
- **Vocabularies:** check against GBIF's vocabularies (https://api.gbif.org/v1/vocabularies).
  - The copies are pinned in `skills/dwc-dp/vocabularies/` by `tools/pin_vocabularies.py`.
  - Which field uses which vocabulary is GBIF's own configuration, gbif/pipelines `pipelines.yaml`
    `vocabularyConfig`.
  - Values outside them are warnings, not errors.
  - `eventCategory` has no GBIF vocabulary, so it isn't checked.

## Needs a human decision

0. **Where GBIF's analyser is more lenient than the guide, or warns where the schema allows**
   `needs-human`
   - `check` follows the analyser's levels. These may be worth raising with its maintainer:
     - a field `type` other than the schema's, a resource `profile` other than
       `tabular-data-resource`, and a relationship the schema doesn't define are warnings, though
       the guide says MUST;
     - a custom field is INFO;
     - a changed `description` is a warning, though the guide (3.4) says it MAY differ;
     - `FK_UNKNOWN_REFERENCE_RESOURCE` for identifiers (weak foreign keys) that point outside the
       package, which the schema allows. Every package with, for example, `recordedByID` and no
       `agent` table gets it;
     - `primaryKey`, `mediatype`, a schema given as a reference, and column order are not checked
       at all; `check` keeps them as its own errors.

1. **Metadata** `needs-human`
   - Found so far: `eml.xml` is optional in the guide.
   - GBIF's crawler forwards `eml.xml` when the package has one, and the `datapackage.json`
     metadata otherwise (gbif/crawler `DwcDpMetasyncCallback`).
   - GBIF's validator checks EML when present (title, creator, EML 2.2.0).
   - Should the plugin write `eml.xml`, descriptor metadata, or both?
