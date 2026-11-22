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
  - Wait for the answer to "MDT overlap" below before writing the data-holder guidance; the table
    mapping can be done now.
- **`validate`: event and material hierarchies** `ready` `tooling`
  - Detect cycles in `parentEvent_fk`, `derivedFromMaterialEntity_fk`, `isPartOfMaterialEntity_fk`
    and other self-references, and report them in plain words.
- **`check`: compressed packages and tables** `ready` `tooling`
  - Read `.gz` tables and a gzipped package (guide section 3), with tests.
- **`load`: spreadsheets without the excel extension** `ready` `tooling`
  - Reading `.xlsx` needs DuckDB's excel extension, which downloads on first use.
  - Find out whether it can be bundled or installed once, and otherwise document saving sheets as
    CSV.

## Needs a human decision

1. **Publishing route** `needs-human`
   - Should the plugin end at a validated package, or also take it to an IPT with DwC-DP support
     (https://dwcdp-ipt.gbif-test.org, the IPT `dwc-dp` branch)?
   - Does GBIF ingest DwC-DP 1.0 yet?
2. **Metadata** `needs-human`
   - Should the plugin write `eml.xml` (as the MDT and the IPT do), the package-level properties
     of the Data Package specification, or both?
3. **Examples before 1.0** `needs-human`
   - gbif/dwc-dp-examples still uses keys from before 1.0, and the guide's own example in section 2
     too. Should this project raise that upstream (issues or PRs in gbif/dwc-dp-examples and
     tdwg/dwc), or only work around it here?
4. **MDT overlap** `needs-human`
   - Should eDNA and metabarcoding data holders be sent to the MDT, which already writes DwC-DP
     1.0, with this plugin covering only what the MDT can't?
5. **Darwin Core Archive input** `needs-human`
   - Should the plugin also convert existing Darwin Core Archives to DwC-DP?
6. **Controlled vocabularies** `needs-human`
   - The JSON schemas have no enumerations, only usage notes such as "Recommended best practice is
     to use a controlled vocabulary".
   - TDWG's PostgreSQL build (`build/dwc-dp/generate_sql.yaml` in tdwg/dwc) adds ENUMs, and they
     differ from the schema examples:
     - `eventCategory`: the SQL ENUM has `Event`, `MaterialGathering`, `Occurrence`,
       `OrganismInteraction` and `Survey`, while the schema examples have `material collection`,
       `occurrence`, `survey` and `context`;
     - `occurrenceStatus`: the ENUM has `detected`, `present`, `notDetected` and `absent`.
   - Which values should `validate` require, warn about, or leave alone?
