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
- **Run GBIF's DwC-DP analyser from the plugin** `ready` `tooling`
  - gbif/dwc-dp-analyser (Apache-2.0) is the validator GBIF's crawler runs on every DwC-DP it
    downloads. Each release ships a jar (any OS, Java 17+), `.deb`, `.rpm`, Arch and Windows
    packages. Homebrew users can use Wisienkas/homebrew-dwc-dp-analyser.
  - Add `dwcdp.py analyse <folder>`:
    - finds `dwc-dp-analyser` on the PATH, or `java -jar $DWC_DP_ANALYSER_JAR`;
    - runs it with `--output-format JSON --report VERIFY`;
    - reads `isValid`, `result.descriptorValidation.issues[]` (`severity`, `violationType`,
      `message`, `location`) and `result.emlValidation`;
    - reads each `result.resourceAnalysisResults[]`: `foreignKeyViolations`,
      `primaryKeyViolation` and `dataTypeViolations`, each with counts and samples;
    - says each in plain words, and exits as the analyser does (0 valid, 2 not valid, 1 couldn't
      run).
  - When it isn't installed, say how to install it for their system, and stop. Never download
    or install it on their behalf.
  - It fetches the DwC-DP 1.0 profile and table schemas from rs.tdwg.org (only 0.1 and 1.0_DEV
    are bundled), so it needs the network; no data is sent. With `--offline-schemas` a 1.0
    package fails as `UNRECOGNIZED_PROFILE_VERSION`. Say so before running it.
  - Record the analyser version it was tested with (0.0.16), and say when theirs differs.
  - Tests use a recorded JSON report as a fixture, so they run without Java.
  - SKILL.md Stage 7: the package is done when `check` passes and the analyser reports it valid.
    If the analyser can't be installed, say the package passed `check` only.
- **Make `check` agree with the analyser** `ready` `tooling`
  - Found by reading the 0.0.16 source:
    - **Field descriptors:** the analyser compares `title`, `description` and
      `dcterms:isVersionOf` (and `format`, `namespace` and `dcterms:references` when present)
      with the canonical schema, as a warning (`FIELD_DEFINITION_MISMATCH`). `check` compares
      only `type` and `dcterms:isVersionOf`.
    - **Duplicate field names in a resource:** an error (`FIELD_DUPLICATE`), which `check`
      doesn't test.
    - **Top-level `name`:** a warning when missing (`MISSING_NAME`, RECOMMENDED by Frictionless).
      `package` writes no `name`; add `--name`, and ask the data holder for it.
    - **The profile's JSON Schema:** validated (`JSON_SCHEMA_VIOLATION`, a warning). `check`
      tests only parts of it, for example the five properties each field must have.
    - **EML:** well-formed, `<title>`, `<creator>` and the EML 2.2.0 XSD. These don't affect
      `isValid`.
  - Beyond the analyser, `check` and `validate` also cover:
    - required values that are empty (the analyser checks only that the field is declared);
    - `minimum`/`maximum`;
    - references by public identifier (weak foreign keys);
    - the conceptual model's one-evidence rule;
    - GBIF vocabularies.
    Keep these, as the plugin's own checks.
  - Done when the analyser and `check` agree on every fixture package (the recorded reports),
    with differences either fixed or listed in `references/package.md` with their reason.
- **Run the analyser in CI** `ready` `tooling`
  - In `test.yml`:
    - download the pinned release jar;
    - verify it against the release's `checksums.txt`;
    - run it on the packages the tests build;
    - fail on a verdict different from the recorded one.
  - This is how a new analyser release is noticed. Moving to a new release is its own PR.
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

1. **Metadata** `needs-human`
   - Found so far: `eml.xml` is optional in the guide.
   - GBIF's crawler forwards `eml.xml` when the package has one, and the `datapackage.json`
     metadata otherwise (gbif/crawler `DwcDpMetasyncCallback`).
   - GBIF's validator checks EML when present (title, creator, EML 2.2.0).
   - Should the plugin write `eml.xml`, descriptor metadata, or both?
