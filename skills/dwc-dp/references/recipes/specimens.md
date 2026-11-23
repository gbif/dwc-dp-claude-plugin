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

The worked example is `tests/fixtures/specimens-beetles/`: a made-up beetle collection export with
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
   specimen and `materialEntityCategory` `tissue`.
5. **Determinations:**
   - one identification per row, of the specimen (`materialEntity_fk`);
   - `isAcceptedIdentification` from their "current" column;
   - the name as written in `verbatimIdentification`, and the name without the author in
     `scientificName`, with `scientificNameAuthorship`;
   - `identifiedBy` and `dateIdentified`;
   - for a qualified name, `taxonFormula` and an `identification-taxon` row (see the choices
     below).

`validate` and `check` pass on it.

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
- **`materialEntityCategory` and `materialEntityType`.**
  - The schema recommends "a limited, tightly controlled vocabulary" for the category, and gives
    examples (`preserved`, `living`, `fossilized`, `tissue`, `DNA extract`, `non-biological`,
    `human-made`). For the type it gives examples such as `Pinned object/specimen`,
    `Microscope slide` and `Taxidermy mount`, and no list.
  - Propose from the examples, and leave a type empty when theirs fits none.
- **When derived material was taken.**
  - A derivation can be an event of its own (`derivationEvent_fk`, "material derived during
    event"), with its date and who took it.
  - The schema's `eventCategory` examples have no category for it, so ask what to call it. Until
    then, keep the date in `materialEntityRemarks`, as the example does.
- **The current name on the material.**
  - `material` has its own identification fields (`scientificName`, `identifiedBy`,
    `typeStatus` and others), as well as the `identification` table.
  - The schema doesn't say how they relate, for example whether the material's fields should
    repeat the accepted determination. bgbm's mapping has that copy written but commented out.
  - Until this is settled, the example leaves them empty and puts every determination in
    `identification`. Tell the data holder it is an open question.
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
- **Institution and collection codes.** Use the codes they publish under; never fill them in from
  memory. If the export lacks them, ask.
- **Agents.**
  - Names in `collectedBy`, `recordedBy` and `identifiedBy` are enough to start.
  - Add `agent` rows (and `collectedBy_fk`, `identifiedBy_fk` or `*-agent-role` rows) when they
    have identifiers such as ORCIDs, or several people per role in a given order.

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
  (*of a* and *based on* are different links). `validate` warns only when one identification is
  based on more than one kind of evidence.
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
