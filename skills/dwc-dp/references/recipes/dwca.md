# Recipe: Darwin Core Archives

## When it applies

The data holder already publishes, or has prepared, a Darwin Core Archive: a `.zip` (or folder)
with a `meta.xml`, a core file (Occurrence, Event, or Taxon) and possibly extensions
(MeasurementOrFact, extended MeasurementOrFact, Multimedia, DNA derived data, ResourceRelationship,
Identification History...), and usually an `eml.xml`.

The archive's columns are already Darwin Core terms. That makes most of the work a lookup, but not
all of it. A Darwin Core Archive is a star: one flat core row with extensions around it. DwC-DP is a
web of tables, and one core row usually becomes several rows in several tables. Where the split goes
is where the choices are.

## Stage the archive and look terms up

```text
dwcdp.py load-dwca archive.zip
dwcdp.py suggest src_dwca_occurrence
```

- **`load-dwca`** stages the core as `src_dwca_<row type>`, with `id` as its record key, and each
  extension the same way, with `coreid`. Columns are named after their terms, and `meta.xml`
  defaults are filled in. It also records each column's term URI.
- **`suggest`** looks each column up by its term. Every DwC-DP field states the term it is a
  version of (`dcterms:isVersionOf`), so "by term: event.eventDate" is the schema's own answer, not
  a guess from the name.
- **A term that several tables have** (`scientificName`, `recordedBy`, `identifiedBy`): the choice
  is which one, and the sections below cover it.
- **"No DwC-DP field is a version of …":** the term has no direct home. The common cases follow.

## Terms without a field of their own

| Term | In DwC-DP |
|---|---|
| `basisOfRecord` | expressed by the tables. A `PreservedSpecimen`, `FossilSpecimen`, `LivingSpecimen` or `MaterialSample` becomes a `material` row, the evidence for its occurrence. A `HumanObservation` or `MachineObservation` is an occurrence without material |
| `individualCount` | `occurrence.organismQuantity` with `organismQuantityType` `individuals` |
| `associatedMedia` | rows in `media`, linked to what they show (`occurrence-media`, `material-media`) |
| `measurementType`, `measurementValue`, `measurementUnit`, … | assertions; see below |
| `kingdom` … `genus`, `specificEpithet` and other ranks | only on `identification` (and `identification-taxon`), not on `occurrence` or `material` |
| `dcterms:creator` of an image | an `agent` and a `media-agent-role` (the media table has no creator field) |
| a dataset-level term (`datasetName`, `institutionID`, `license` of the dataset) | the package's metadata, or the field on the table it describes (`material.institutionID`) |

## Occurrence core

Each row holds an organism's state, and the place, time and collector. If it is a specimen, it
also holds the specimen and its name. Split it:

1. **Events:**
   - **Grouping:** an occurrence's place and time are its event's. Rows that share a collecting
     event (the same `fieldNumber`, or the same `eventID` if the archive has one) can share one
     event. Otherwise one event per row.
   - **`eventCategory`** is required, and the archive doesn't have it. Ask, as in the other
     recipes.
2. **Occurrences:** one per row, with `occurrenceID`.
   - `occurrenceStatus` is required in DwC-DP but often missing in archives. Write `detected` only
     with the data holder's agreement that the rows record organisms found.
3. **Material:** for specimens (by `basisOfRecord`), a material row with `catalogNumber`,
   `institutionCode`, `preparations` and the rest, the evidence for the occurrence
   (`evidenceForOccurrence_fk`).
4. **Identifications:**
   - one per row, *of* the material for specimens and *based on* the occurrence for observations;
   - the name and its higher ranks go here, the only table with them;
   - an Identification History extension gives one identification per row, with
     `isAcceptedIdentification` marking the core's current one;
   - the open question about the name fields on `occurrence` and `material` applies (see
     `specimens.md`).

The worked example is `tests/fixtures/dwca-occurrence-core/`:
- **The archive:** made up, two pinned specimens from one field trip and a photographed
  observation, without `occurrenceStatus`, with a Simple Multimedia extension and a
  MeasurementOrFact extension.
- **The mapping:**
  - the two specimens share an event by their `fieldNumber`;
  - the specimens become material;
  - the photo becomes media with `occurrence-media`;
  - the body lengths become `material-assertion` rows.
- **Multimedia:** `dcterms:format` holds a MIME type there, so it goes in `media.format`. In
  DwC-DP, `formatIRI` is the version of `dcterms:format` and is meant for an IRI.

## Event core

The events are the core, with occurrences as an extension (`coreid` is the event).

1. **Events:** one per core row, with `parentEventID` as `parentEvent_fk`. `eventCategory` comes
   from the data holder: for example `context` for a project and `survey` for its samples.
2. **Surveys:** `samplingProtocol`, `sampleSizeValue`/`Unit` and `samplingEffort` exist only on
   `survey`. Add a survey row for each event that has them (see `survey.md`).
3. **Occurrences:** from the extension, with `event_fk` from `coreid`. Values such as `present`
   and `absent` are deprecated in GBIF's OccurrenceStatus vocabulary. `vocab OccurrenceStatus`
   names their replacements (`detected`, `notDetected`), to be used with agreement.
4. **Identifications:** based on each occurrence, as above.

The worked example is `tests/fixtures/dwca-event-core/`:
- **The archive:** made up, a benthic survey with two grab samples, occurrences with `present` and
  `absent`, and extended MeasurementOrFact rows: water depth and sediment type of the samples, and
  the wet mass of one occurrence.
- **The mapping:**
  - the survey is the context;
  - each sample is a survey with its protocol and sample size;
  - water depth goes to the event's depth fields, which are dedicated fields;
  - the other eMoF rows become assertions.

## MeasurementOrFact and extended MeasurementOrFact

They become assertions (`references/assertions.md`). The evidence:
- **The tables:** every `*-assertion` table is a version of `dwc:MeasurementOrFact`.
- **The IRI fields:** `assertionTypeIRI` and `assertionValueIRI` are versions of
  `dwciri:measurementType` and `dwciri:measurementValue`.
- **The literal terms:** `assertionType`, `assertionValue`, `assertionUnit` and the rest are new
  Darwin Core terms (issued 2026-05-26) that don't formally replace the measurement terms. Mapping
  them is a match by meaning: say so to the data holder.

| MeasurementOrFact | Assertion |
|---|---|
| `measurementID` | `assertionID` |
| `measurementType` | `assertionType` |
| `measurementTypeID` (eMoF) | `assertionTypeIRI` |
| `measurementValue` | `assertionValue` |
| `measurementValueID` (eMoF) | `assertionValueIRI` |
| `measurementUnit` | `assertionUnit` |
| `measurementUnitID` (eMoF) | `assertionUnitIRI` |
| `measurementAccuracy` | `assertionError` |
| `measurementDeterminedBy` | `assertionBy` |
| `measurementDeterminedDate` | `assertionMadeDate` |
| `measurementMethod` | `assertionProtocols` |
| `measurementRemarks` | `assertionRemarks` |

**Which table** is the question the archive often doesn't answer:
- A MeasurementOrFact row hangs on a core row. In an Occurrence core it may describe the organism
  (`occurrence-assertion`), the specimen (`material-assertion`) or the site (`event-assertion`).
- In an Event core, an eMoF row with an `occurrenceID` is about that occurrence. One without is
  about the event, or about material if a sample is meant.
- Ask, using the table in `assertions.md`.
- **Measurements that have a dedicated field** go there instead: depth, elevation, sample size,
  effort, mass of material.

## Other extensions

- **Simple Multimedia, Audubon Media:** `media`, plus the `*-media` table of what it shows; the
  licence in `media.license`; the creator as an agent.
- **DNA derived data:** see `edna.md`.
  - The protocol terms (`target_gene`, `pcr_primer_forward`, ...) go to `molecular-protocol`, one
    row per distinct protocol rather than per occurrence.
  - `DNA_sequence` goes to `nucleotide-sequence.sequence`.
  - The reads become `nucleotide-analysis` rows. In these archives they are usually the
    occurrence's `organismQuantity` with `organismQuantityType` `DNA sequence reads`, and
    `sampleSizeValue` holds the sample's total reads.
  - Whether occurrences are kept is the data holder's choice.

  No worked example yet.
- **ResourceRelationship:** `resource-relationship` for general relationships, or
  `organism-interaction` when it is an observed interaction between two occurrences
  (`observations.md`). Ask which it is.
- **Identification History:** one `identification` row per determination (`specimens.md`).

## Taxon core

A checklist. DwC-DP 1.0 has no table for a checklist of taxa (`identification-taxon` holds the taxa
of an identification), so whether and how a Taxon-core archive can be translated is an open
question. Say so, and don't force one into the tables.

## Pitfalls

- **Extension rows whose `coreid` has no core row:** the links fail in `validate`.
- **One event per row when rows share one,** or the opposite. Neither shows in `validate`; agree on
  the grouping first.
- **`present`/`absent`, `PreservedSpecimen` and other values copied as they are:** `validate` warns
  about deprecated vocabulary values. `basisOfRecord` has no field at all.
- **Higher ranks lost** by putting the name only on `occurrence`: there is no `kingdom` there.
- **Dataset terms repeated on every row** (`datasetName`, `license`): they belong to the package's
  metadata.
- **The archive's `eml.xml`:** `package --eml` includes it as it is. `check` checks that it is
  well-formed and has a title and creator.

## Sources

- Darwin Core text guide, https://dwc.tdwg.org/text/, for `meta.xml`.
- DwC-DP 1.0 table schemas (the vendored copies): every field's `dcterms:isVersionOf`, which
  `suggest` uses, and the `*-assertion` tables as versions of `dwc:MeasurementOrFact`.
- Darwin Core term versions (tdwg/dwc `vocabulary/term_versions.csv` at the pinned commit): the
  assertion terms, issued 2026-05-26, with no `replaces`.
- GBIF's OccurrenceStatus vocabulary (the pinned copy), for `present`/`absent`.
- The GBIF Metabarcoding Data Toolkit's Darwin Core Archive writer
  (gbif/metabarcoding-data-toolkit-backend, `converters/dwc.js`): reads as `organismQuantity`
  with `organismQuantityType` "DNA sequence reads", and totals in `sampleSizeValue`.
