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

- **Recipe: Darwin Core Archives** `ready` `recipe`
  - `load-dwca` stages an archive. The recipe covers the usual cores (Occurrence, Event) and
    extensions (MeasurementOrFact, Multimedia, DNA derived data, ResourceRelationship), and which
    DwC-DP tables their terms go to.
  - MeasurementOrFact rows become assertions: the assertion tables are versions of
    `dwc:MeasurementOrFact`. Each row goes to the table of the thing it is about (event,
    occurrence or material), which the archive's core alone doesn't always say.
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

## Done since

- **Recipe: surveys** (2026-11-23): `references/recipes/survey.md`, with the worked example
  `tests/fixtures/survey-point-counts/` and the test `SurveyRecipe`. `package` now writes whole
  numbers without `.0`.
- **Recipe: specimens and collections** (2026-11-23): `references/recipes/specimens.md`, with the
  worked example `tests/fixtures/specimens-beetles/` and the test `SpecimensRecipe`.
- **Recipe: observations, interactions and camera traps** (2026-11-23):
  - `references/recipes/observations.md`;
  - worked examples `tests/fixtures/observations-pollinators/` and
    `tests/fixtures/observations-camtrap/` (from Camtrap DP 1.0.2 tables);
  - the test `ObservationsRecipe`.
- **Recipe: eDNA** (2026-11-23):
  - `references/recipes/edna.md`, built around several markers on the same samples, with one
    `molecular-protocol` per marker;
  - the worked example `tests/fixtures/edna-two-markers/`;
  - the test `EdnaRecipe`.
- **Material in the recipes** (2026-11-23):
  - `specimens.md`: specimens kept as several pieces (parts and derived material), with
    `tests/fixtures/specimens-mammal-parts/`;
  - `edna.md`: kept samples, filters and extracts, each derived from the one before, with the
    analyses pointing to the extract;
  - `survey.md`: trap catches kept as bulk samples, with vouchers and metabarcoding, in
    `tests/fixtures/survey-malaise-bulk/`.
- **Assertions** (2026-11-23):
  - `references/assertions.md`: a dedicated field first; which thing a value is about; how to fill
    the fields; never guess a unit;
  - `dwcdp.py suggest`, which lists each source column's possible fields or flags it as an
    assertion candidate;
  - SKILL.md stages 1 and 2 use them, and the eDNA, specimen and point-count examples each map a
    measurement as an assertion.

## Decided

- **The goal is a valid package.** The plugin stops when `check` passes; publishing is not part
  of it.
- **Upstream examples:** don't raise their pre-1.0 state in gbif/dwc-dp-examples or tdwg/dwc.
- **eDNA:** no referral to the MDT; the plugin builds DwC-DP for eDNA as for any other data.
- **Darwin Core Archives:** yes, help translate them to DwC-DP (`load-dwca`, and the recipe above).
- **Identification qualifiers** (2026-11-23):
  - meanings from https://en.wikipedia.org/wiki/Open_nomenclature, which says placement is not
    fixed, so the data holder confirms which part was uncertain;
  - `taxonFormula` as in Arctos (`A cf.`, `A aff.`), with the named taxon in
    `identification-taxon`;
  - `scientificName` only the part that is certain.
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

1. **The identification fields on `material` and `occurrence`** `needs-human`
   - `material` and `occurrence` both have `scientificName`, `identifiedBy` and other
     identification fields (`material` also `typeStatus`), as well as the `identification` table
     with `isAcceptedIdentification`. The schema doesn't say how they relate.
   - Should the material repeat the accepted determination, hold something else, or stay empty
     when `identification` is used? bgbm's mapping has the copy commented out.
   - The specimens recipe leaves them empty until this is settled.
2. **Where an amplicon study's reference database goes** `needs-human`
   - `otu_db` is described as the reference database "used to cluster new genomes in
     "species-level" OTUs" and `ref_db` as for ORF annotation. Both are MIxS terms written for
     genomes, and GBIF's DNA derived data extension has the same descriptions.
   - The MDT puts the taxonomy reference database in `otu_db`, and the eDNA recipe follows it. Is
     that the intended term?
3. **`processedTotalReadCount`** `needs-human`
   - The schema's description reads as per sequence ("for a processed dwc:NucleotideSequence").
   - The eDNA recipe reads it as the sample's total for one marker, as the MDT writes it, because
     `readCount` already holds the per-sequence reads. Confirm.
4. **`eventCategory` for a derivation event** (a tissue taken from a specimen) `needs-human`
   - The schema's examples have none. Is there a value to use, or should the date stay in
     `materialEntityRemarks`?
5. **Metadata** `needs-human`
   - Found so far: `eml.xml` is optional in the guide.
   - GBIF's crawler forwards `eml.xml` when the package has one, and the `datapackage.json`
     metadata otherwise (gbif/crawler `DwcDpMetasyncCallback`).
   - GBIF's validator checks EML when present (title, creator, EML 2.2.0).
   - Should the plugin write `eml.xml`, descriptor metadata, or both?
