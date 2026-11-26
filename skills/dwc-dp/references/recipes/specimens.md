# Recipe: specimens and collections

## When it applies

The data come from a collection: catalogued specimens, lots, samples or living material, usually
exported from a collection database or spreadsheet. The files usually are:

- one row per specimen, with the collecting event (place, date, collector, field number) repeated
  on every row;
- determinations, either as columns of the current name or as a history table;
- preparations and derived material (tissues, slides, DNA extracts);
- sometimes images, loans and type information.

## Tables

| Table | What it holds (from the schema) |
|---|---|
| `event` | the collecting event, written once for all specimens from it |
| `material` | "An entity that can be identified, exist for some period of time, and consist in whole or in part of physical matter while it exists": specimens, lots, tissues and extracts. It points to its collecting event (`collectionEvent_fk`), to material it was derived from (`derivedFromMaterialEntity_fk`) or is part of (`isPartOfMaterialEntity_fk`), and to an occurrence it is evidence for (`evidenceForOccurrence_fk`) |
| `occurrence` | the organisms' state when collected (sex, life stage, how many), when the data holder records it |
| `identification` | "A classification of a resource according to a classification scheme"; one row per determination, *of a* material (`materialEntity_fk`), with `isAcceptedIdentification` marking the current one |
| `identification-taxon` | "A construct of components and positions of dwc:Taxa in a dwc:Identification": the taxa in a formula such as a hybrid, in `taxonSortOrder` |

`dwcdp.py order` puts them in this order: event, occurrence, material, identification,
identification-taxon.

Add these only when the data have something for them:

- `agent` and the `*-agent-role` tables: collectors and determiners with identifiers (ORCID) or
  several roles;
- `media` and `material-media`: images of specimens;
- `material-identifier`: other numbers;
- `material-assertion`: measurements;
- `usage-policy`: rights per record.

## Keys

- **Specimens:** their stable identifier (a URI or GUID, if the collection has one) as
  `materialEntityID`, which "MUST be preserved in aggregation". Otherwise the catalogue number, and
  say that it is only unique within their collection. The same value can be `materialEntity_pk`.
- **Collecting events:** the field number, when one field number is one collecting event.
  Otherwise a combination they agree on, such as locality, date and collector.
- **Derived material:** its own number (a tissue number), not the parent's.
- **Determinations:** their determination id, if they have one. Otherwise the specimen and the
  date (`NHMD-COL-1002:2025-02-10`), when a specimen is never determined twice on one day.
- **Occurrences:** derived from the specimen (`NHMD-COL-1001:occurrence`), unless they have their
  own.

## Mapping, step by step

There are two worked examples. The first is `tests/fixtures/specimens-beetles/`: a made-up beetle collection export with
four specimens (one a lot of five), five determinations (one superseded, one with "cf.", one with
"aff.") and a tissue sample. Its `mapping.sql` is the full mapping.

1. **Collecting events:** `SELECT DISTINCT` on the field number. The place, date and collector are
   written once, with `eventCategory` `material collection` (one of the schema's examples).
2. **Occurrences:** one per specimen, with `occurrenceStatus` `detected` (required), the sex, and
   the count of a lot as `organismQuantity` with `organismQuantityType`.
3. **Specimens:**
   - the catalogue number as `materialEntityID` and `catalogNumber`;
   - `collectionEvent_fk` and `evidenceForOccurrence_fk`;
   - `collectedBy`, `preparations`, `materialEntityCategory` `preserved`, and the label text as
     `verbatimLabel`.
4. **The tissue:** its own material row with `derivedFromMaterialEntity_fk` pointing to the
   specimen and `materialEntityCategory` `tissue`. Who took it and when is a `material-agent-role`
   row (role `sampled by`, date in `agentRoleDate`).
5. **Determinations:**
   - one identification per row, of the specimen (`materialEntity_fk`). It also points to the
     specimen's occurrence (`occurrence_fk`), because GBIF takes an occurrence's name from its
     accepted identification (SKILL.md, Stage 7);
   - `isAcceptedIdentification` from their "current" column;
   - the name as written in `verbatimIdentification`, and the name without the author in
     `scientificName`, with `scientificNameAuthorship`;
   - `identifiedBy` and `dateIdentified`;
   - for a qualified name, `taxonFormula` and an `identification-taxon` row (see the choices
     below).
6. **Measurements:** the elytron length has no field, so it is a `material-assertion` row about the
   specimen, with the unit from the column name (`references/assertions.md`).

`validate` and `check` pass on it.

### A specimen kept as several pieces: `tests/fixtures/specimens-mammal-parts/`

Made-up mammal specimens:
- a pine marten kept as skin, skull and postcranial skeleton (the skeleton on loan), plus a frozen
  liver sample;
- a badger of which only the skull is kept.

Each piece has its own number in `parts.csv`.

1. **The specimen as a whole:** a material row for the catalogue number, the thing the collecting
   event, the occurrence and the determination refer to. Its `preparations` lists the pieces
   (`skin | skull | postcranial skeleton`), so the record is complete on its own too.
2. **Each part:** a material row with its own number, `isPartOfMaterialEntity_fk` pointing to the
   specimen, and its own `preparations` and `disposition` (`on loan` for the skeleton). What the
   piece is goes in `materialDescription`.
3. **The tissue:** derived from the specimen (`derivedFromMaterialEntity_fk`), not a part of it,
   with `materialEntityCategory` `tissue`, and who took it and when as a `material-agent-role`
   row.
4. **The determination:** one, of the specimen as a whole, not of each piece.

## Choices the data holder makes

- **Whether specimens get occurrences.**
  - In the conceptual model, an occurrence is an organism's state at a place and time, and
    material is evidence for it.
  - Use one when they record that state (sex, life stage, behaviour, count) or when specimens and
    observations should be counted together.
  - The examples differ: bgbm's mapping fills `evidenceForOccurrence` from its input, while
    dissco's output has the column empty for all 300 specimens.
  - When the export has nothing about the organisms' state, the specimens can stand alone: no
    occurrence, no `evidenceForOccurrence_fk`.
- **What one material row is.**
  - A specimen, a lot (a vial of five beetles), a sheet with several plants, a part of a specimen
    (`isPartOfMaterialEntity_fk`) or something derived from one (`derivedFromMaterialEntity_fk`).
  - Use the units their catalogue numbers.
- **Pieces of one specimen.** There are three ways, and they can be mixed:
  - **Listed:** a list in the specimen's `preparations`, the schema's own example being
    `skin | skull | skeleton`. Enough when the pieces have no numbers, storage or loans of their
    own.
  - **Parts:** a material row per piece, "part of" the specimen. Needed when a piece has its own
    number, preparation, place or disposition, for example a skull on loan.
  - **Derived:** "derived from" the specimen, for material made from it, such as a tissue sample,
    a DNA extract or a cast.

  Whether a given piece is a part or derived is theirs to say. The schema defines the two links
  ("of which this dwc:MaterialEntity is a part"; "from which this dwc:MaterialEntity was derived")
  and leaves the line to them. The example treats skin, skull and skeleton as parts, and the
  frozen liver as derived.
- **Determinations of pieces.** Usually the determination is of the specimen as a whole. A piece
  gets its own identification only when it was identified on its own, for example a tissue
  barcoded later.
- **`materialEntityCategory` and `materialEntityType`.**
  - The schema recommends "a limited, tightly controlled vocabulary" for the category, and gives
    examples (`preserved`, `living`, `fossilized`, `tissue`, `DNA extract`, `non-biological`,
    `human-made`). For the type it gives examples such as `Pinned object/specimen`,
    `Microscope slide` and `Taxidermy mount`, and no list.
  - Propose from the examples, and leave a type empty when theirs fits none.
- **Recording a derivation.** No event is needed:
  - `derivedFromMaterialEntity_fk` says what the material was derived from. The link to a
    derivation event (`derivationEvent_fk`) is optional.
  - `material` has no date field for a derivation, so choose the lightest form that holds what they
    know:
    1. **Just the link,** when they record nothing about the act.
    2. **Who and when:** a `material-agent-role` row, with the person as an `agent`, a role such as
       `sampled by` or `extracted by`, and the date in `agentRoleDate` ("An interval during which
       a dcterms:AgentRole was in effect"). The examples do this.
    3. **A derivation event:** only when they also record where or how (a protocol), or several
       pieces taken in one act. Its `eventCategory` is required, and neither the schema's examples
       nor TDWG's PostgreSQL build has one for a derivation, so ask what to call it.
  - The role names are theirs: the schema only recommends "a controlled vocabulary for the roles
    appropriate to the class of resource".
- **The current name on the material.**
  - Names go in `identification`, with `isAcceptedIdentification` on the current one. The
    material's own identification fields (`scientificName`, `identifiedBy`, `typeStatus` and
    others) stay empty when it has an identification, which is the maintainers' rule
    (2026-11-23). bgbm's mapping has the copy onto the material commented out too.
  - `validate` warns when a material repeats a name it has an identification for.
- **Qualifiers such as "cf." and "aff.", and hybrids.** These are open nomenclature
  (https://en.wikipedia.org/wiki/Open_nomenclature):
  - **cf.** ("compare with") marks an identification as uncertain;
  - **aff.** marks a probably undescribed species related to the named one, "but is not
    identical to" it.
  - There are no strict conventions about where the qualifier stands or exactly what it doubts.
    So ask the data holder, or their determiners, which part of the name was uncertain.

  How to write them:
  - **The name as written** stays in `verbatimIdentification`, always.
  - **`taxonFormula`** says how the name is qualified. The schema recommends the Arctos formula
    vocabulary, whose examples include `A`, `A cf.`, `A aff.`, `A ?`, `A sp.`, `A or B` and
    `A x B`. In Arctos, `A cf.` and `A aff.` put the qualifier after taxon A as a whole
    (ArctosDB/arctos-archive `form/taxonNameBuilder.cfm`).
  - **The named taxon** goes in `identification-taxon` as taxon A (`taxonSortOrder` 1). A
    formula with two taxa (`A x B`, `A or B`) has a second row.
  - **`scientificName`** holds only what the determiner is sure of: usually the genus, when the
    qualifier stands before the epithet and doubts only the species. Never the named species of an
    "aff.", because the specimen is not that species. For a "cf." it would state as certain what
    the determiner doubted.

  The example does this for "Pterostichus cf. niger" and "Amara aff. aenea":
  - `scientificName` is `Pterostichus` and `Amara`, with `taxonRank` `genus`;
  - `taxonFormula` is `A cf.` and `A aff.`;
  - taxon A is `Pterostichus niger` and `Amara aenea`.

  Its mapping reads the qualifier from the second word of the name. That works only because the
  data holder confirmed their names are always written "Genus qualifier epithet".
- **Type status.**
  - Both `material` and `identification` have `typeStatus`.
  - The example puts it on the determination that carries the name. Ask which their type
    information belongs to.
  - GBIF reads it with its TypeStatus vocabulary; `vocab TypeStatus` lists the concepts.
- **Fossils, subfossils, and specimens with an age or stratigraphy:** see `paleo.md`.
- **Institution and collection codes.** Always ask which institution and collection hold the
  material, and whether another institution owns it (SKILL.md, Stage 3). Use the codes they publish
  under; never fill them in from memory. If the export lacks them, ask.
- **`institutionID` and `collectionID`.** The schema's notes recommend "a globally unique and
  resolvable identifier from a collections registry", such as ROR or GRSciColl
  (https://scientific-collections.gbif.org/). `grscicoll` looks codes up there:
  - It sends only the distinct codes (and `--country`, if given) to GBIF's GRSciColl API, so ask
    first. Their records stay on their machine.
  - `grscicoll material` (or a source table) looks up each distinct combination of
    `institutionCode`, `collectionCode`, `institutionID` and `collectionID`.
    `grscicoll --institutionCode NHMD --collectionCode C-F --country DK` looks up one.
  - It prints the match and its status, any alternatives, and every identifier GRSciColl holds for
    each: its page and key, ROR, Wikidata, Index Herbariorum and others.
  - A match on a code alone is `DOUBTFUL`, so show them the name and country and let them confirm.
  - Show them all the identifiers and let them choose which goes in each field. The schema's
    examples include ROR and GRSciColl page URLs for `institutionID`, and a GRSciColl page URL for
    `collectionID`.
  - No match, or several: ask them. Never pick one.
- **Agents.**
  - Names in `collectedBy`, `recordedBy` and `identifiedBy` are enough to start.
  - Add `agent` rows (and `collectedBy_fk`, `identifiedBy_fk` or `*-agent-role` rows) when they
    have identifiers such as ORCIDs, or several people per role in a given order.
  - With `identifiedBy_fk`, also fill `identifiedByID` with the agent's `agentID`: GBIF's indexing
    finds the identifier through it (SKILL.md, Stage 3).
- **GBIF and the specimen behind an occurrence.** GBIF's indexing currently finds an occurrence's
  material through `material.evidenceForOccurrenceID`. That field was in a draft of DwC-DP
  (rs.gbif.org, `1.0_DEV`) but is not in DwC-DP 1.0, which has only `evidenceForOccurrence_fk`. So
  it can't be filled without a custom field, which the guide says a package should not have, and
  GBIF may not attach the material's details to the occurrence. Tell them. It is GBIF's to fix,
  not theirs; the name still reaches GBIF through the identification (SKILL.md, Stage 7).

## Pitfalls

- **One field number for several collecting events,** such as the same number reused on two
  dates: the `SELECT DISTINCT` gives two events with the same key, and `validate` reports a
  duplicate `event_pk`. Ask how to tell them apart.
- **More than one accepted determination for a specimen:** `validate` doesn't catch it. Check with
  `sql`: `SELECT materialEntity_fk FROM identification WHERE isAcceptedIdentification GROUP BY 1
  HAVING count(*) > 1`.
- **The author inside the name column,** such as `Carabus nemoralis O.F. Müller 1764`:
  `scientificName` is "not including authorship". Ask before splitting, and keep the original in
  `verbatimIdentification`.
- **An identification both of a material and based on an occurrence:** allowed by the schema
  (*of a* and *based on* are different links), and what the examples do, so that GBIF finds the
  name. `validate` warns only when one identification is based on more than one kind of evidence.
- **An occurrence without an accepted identification pointing to it,** or with several: GBIF
  indexes it without a name. `validate` warns.
- **Type status values outside GBIF's vocabulary,** such as `type` or `typus`: `validate` warns.

## Sources

- DwC-DP 1.0 table schemas `material`, `identification`, `identification-taxon`, `occurrence` and
  `event` (the vendored copies), including the field notes quoted above.
- Darwin Core conceptual model, https://dwc.tdwg.org/cm/, sections 2.3 to 2.5 (occurrences,
  material entities, identification).
- gbif/dwc-dp-examples at `a9994e8f72` (2026-10-21), from before 1.0, read for how they split the
  data:
  - **`material/bgbm`** (a herbarium): its mapping fills `evidenceForOccurrence` from the input,
    and the copy of the accepted determination onto the material is commented out;
  - **`material/dissco`:** every determination as an identification with
    `isAcceptedIdentification`, determiners in `identification-agent-role`, and taxa in
    `identification-taxon`. Its `evidenceForOccurrence` column is empty;
  - **`material/cyanolichens`:** input data only.
- Open nomenclature, https://en.wikipedia.org/wiki/Open_nomenclature, for the meaning of "cf." and
  "aff."; ArctosDB/arctos-archive `v7.0/form/taxonNameBuilder.cfm` for how Arctos writes its
  formulas.
- GBIF's TypeStatus and Sex vocabularies (the pinned copies).
