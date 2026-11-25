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
| `associatedTaxa`, `associatedOccurrences` | not assertions. When they name organisms seen with this one at the find, each becomes an occurrence in the same event, with its identification, and an `organism-interaction` (`interactions.md`). `associatedOrganisms` has a field on `organism`, but an observed partner is still an interaction |
| `dynamicProperties` | look inside: a JSON key may be a dedicated field (`Substrate` is `occurrence.substrate`), an assertion, or part of an interaction |
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
   (`evidenceForOccurrence_fk`). Ask which institution and collection hold the specimens, even when
   the archive has codes: a code alone may be shared by several institutions, and a row without one
   needs an answer (SKILL.md, Stage 3). For `institutionID` and `collectionID`, `grscicoll` can
   propose registry identifiers from the codes (`specimens.md`).
4. **Identifications:**
   - one per row, *based on* the occurrence, which is where GBIF reads the name from, and for
     specimens also *of* the material;
   - the name and its higher ranks go here, the only table with them;
   - an Identification History extension gives one identification per row, with
     `isAcceptedIdentification` marking the core's current one;
   - the name fields on `occurrence` and `material` stay empty: names go in `identification` only.

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

### Implicit interactions: `tests/fixtures/dwca-associated-taxa/`

- **The archive:** made up, fungus finds in an Occurrence core. `associatedTaxa` names the tree each
  one grew with (`bøg (Fagus)`), and `dynamicProperties` holds the substrate.
- **The mapping:**
  - each tree is an occurrence in the find's event, named in `identification`;
  - an `organism-interaction` has the fungus as its subject and the tree as the related
    occurrence, with the value as written in `organismInteractionDescription`;
  - the type follows the data holder's rule for the substrate (soil: `mycorrhizal symbiont of`,
    dead wood: `saprophyte of`, bark of living trees: `parasite of`). Other substrates say nothing
    about the tree, so their interactions have no type.

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
- **DNA derived data:** see `edna.md` and the section below.
- **ResourceRelationship:** `resource-relationship` for general relationships, or
  `organism-interaction` when it is an observed interaction between two occurrences
  (`observations.md`). Ask which it is.
- **Identification History:** one `identification` row per determination (`specimens.md`).

## DNA derived data

Archives of metabarcoding data, such as those the GBIF Metabarcoding Data Toolkit writes, are
an Occurrence core with one row per sample and sequence. A DNA derived data extension gives each
row its sequence and protocol. In DwC-DP the result is the eDNA tables (`edna.md`):

1. **Events and material:** one event per `eventID`. A `MaterialSample` row's sample is material.
   In MDT archives the `eventID` also names the sample, so it can key both, with the data holder's
   agreement.
2. **Protocols:** the extension repeats the protocol on every row, so make one `molecular-protocol`
   per distinct combination of target gene, primers, reference database and sequencing method.
   - By term: `target_gene`, `pcr_primer_*`, `otu_db` and `seq_meth` are versions of the same terms
     on `molecular-protocol`.
   - `load-dwca` names the numbered MIxS term columns after their DwC-DP field (`target_gene`
     rather than `0000044`).
3. **Sequences:** one `nucleotide-sequence` per distinct `DNA_sequence`.
   - The extension's term (`http://rs.gbif.org/terms/dna_sequence`) has no DwC-DP version.
     `nucleotide-sequence.sequence` is a version of `dwc:sequence`, so this is a match by meaning.
     Don't confuse it with `molecular-protocol.sequence`, which describes the protocol.
   - When the archive has no sequence ids, a hash of the sequence (`md5(...)`) gives the same key
     for the same sequence in every sample, with agreement.
4. **Analyses:** one per occurrence row:
   - `organismQuantity` becomes `readCount`, when `organismQuantityType` is "DNA sequence reads";
   - `sampleSizeValue` becomes `processedTotalReadCount`, when `sampleSizeUnit` is "DNA sequence
     reads".
   - `suggest` lists `survey.sampleSizeValue` for that term. In these archives it is the sample's
     total reads, which is why it goes to the analysis here: `processedTotalReadCount` is the
     sample's total read count, next to `readCount` (`edna.md`).
5. **Identifications:** one per sequence, based on it. The archive repeats the taxonomy on every row
   of the same sequence.
6. **Occurrences:** the core rows are inferred occurrences. Keeping them is the data holder's
   choice (`edna.md`). The example leaves them out.

The worked example is `tests/fixtures/dwca-dna-derived/`:
- **The archive:** made up in the MDT's shape, two samples and two COI sequences, one of them found
  in both samples and one assigned only to family.
- **The result:**
  - two events and two samples;
  - one protocol;
  - two sequences, keyed by their MD5;
  - three analyses with reads and totals;
  - two identifications.

Pitfall: if the same sequence carries different taxonomy on different rows (assigned twice, or
edited), one identification per sequence gives two rows with one key. `validate` reports the
duplicate; ask which assignment stands, or keep both with `isAcceptedIdentification`.

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
- **`associatedTaxa` as an assertion,** or left out because no field is a version of it: it names
  organisms, so it is an interaction (`interactions.md`).
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
