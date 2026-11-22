# DwC-DP in plain words

Read this before choosing tables. The sources are the DwC-DP 1.0 table schemas in
`../schemas/1.0/` (normative), the DwC-DP guide (https://dwc.tdwg.org/dp/, section 3 is
normative), and the Darwin Core conceptual model (https://dwc.tdwg.org/cm/, which is
non-normative). When this page and the schemas disagree, the schemas win: say so and fix this
page.

## One table per kind of thing

A spreadsheet often has one row that mixes several things: a site visit, the specimen taken on it,
and the name someone gave the specimen. DwC-DP keeps each kind of thing in its own table, one row
per thing, and links the rows. So the visit is written once, and every specimen from it points to
it.

This is what database people call normalisation. For a data holder it means:

- a fact is written once. A visit's date and coordinates sit on the visit, not repeated on each
  specimen;
- things can be counted and corrected one at a time. A second identification of a specimen is a
  new row in `identification`, and the first stays;
- the tables can hold what a flat file can't, such as a sample split into subsamples, or one photo
  showing several organisms.

## Keys: how rows point to each other

Every table that other tables point to has two identifying fields. Use `describe <table>` to see
them.

| Field | Example | What it is | Rule in the schema |
|---|---|---|---|
| `x_pk`, the **package key** | `event_pk` | Unique within its table in this package. Other tables point to it. | "MAY be changed in aggregation to guarantee uniqueness." |
| `xID`, the **public identifier** | `eventID` | The identifier the data holder uses and others cite: a catalogue number, field number or URI. | "MUST be preserved in aggregation." |

So `xID` is theirs and stays as it is. `x_pk` is the package's own wiring, and GBIF may change it
when it combines datasets. They can hold the same value when the data holder's identifier is
unique in that table.

Rows point to other rows in two ways:

- **A link to a row in this package** (`..._fk`, a foreign key): for example `occurrence.event_fk`
  holds the `event_pk` of the event the occurrence happened in. It must match a row in the package.
  `validate` and `check` report each one that doesn't.
- **A reference by public identifier** (`...ID` fields that name another table, such as
  `recordedByID`): this may refer to something inside the package or outside it. For example an
  ORCID for a person who isn't in the `agent` table. The schema says such a field "MAY refer to a
  … within or external to the dataset". `validate` only warns when one matches nothing in the
  package.

Each link has a meaning, the `predicate` in the schema: "occurrence *has context* event",
"material *collected during* event", "identification *based on* occurrence". `describe` prints
them, and they are the plainest way to explain a link.

A few tables point to themselves: `event.parentEvent_fk` ("happened during") builds event
hierarchies, and `material.derivedFromMaterialEntity_fk` records that a tissue sample was taken
from a specimen.

## The main kinds of thing

From the conceptual model:

- **Event** (`event`): "an action, a process, or a set of circumstances occurring at some place
  during some interval of time". In DwC-DP 1.0 the location is a field of the event. Events nest
  through `parentEvent_fk`: a project, then expeditions, then site visits, then single trap
  samples. Each event has a required `eventCategory`, a broad category, and an optional `eventType`
  for the narrow one (`describe event --field eventCategory`).
- **Occurrence** (`occurrence`): an organism at a place and time, in some state. It is also an
  event. It points to its context event with `event_fk`. Recording an absence is also an
  occurrence: `occurrenceStatus` says whether the organism was detected.
- **Organism** (`organism`): the organism itself, for traits that don't change between
  occurrences, such as a tagged animal seen many times.
- **Survey** (`survey`, `survey-target`): an event that is a biotic survey or inventory, with what
  it targeted. With enough detail, it supports inferring absences and abundances.
- **Organism interaction** (`organism-interaction`): two occurrences in one interaction, such as a
  bee visiting a flower, or a predator and its prey.
- **Material** (`material`): something physical: a specimen, a tissue sample, a soil or water
  sample, a DNA extract. It points to the event it was collected during, and to other material it
  was derived from.
- **Identification** (`identification`, `identification-taxon`): naming something. In the schema
  an identification is *of a* material entity or *of an* organism, and *based on* evidence: an
  occurrence, a media item, a nucleotide analysis or a sequence. The conceptual model has it based
  on one kind of evidence. Each new determination is a new row.
- **Nucleotide analysis and sequence** (`nucleotide-analysis`, `nucleotide-sequence`,
  `molecular-protocol`): eDNA and barcoding. An analysis links a sequence to the material and event
  it came from, by a protocol.
- **Agent** (`agent`, plus `*-agent-role` tables): people, groups, organisations, machines and
  software, and the role each had (collector, identifier, owner).
- **Media** (`media`, plus `*-media` tables): images, sound and video, linked to what they show.
- **Assertion** (`*-assertion` tables): a measurement, fact or characteristic of an event,
  occurrence, material and so on, such as water temperature or body length. This is where a
  measured value goes when DwC-DP has no field for it.
- **Protocol, reference, provenance, usage policy** (`protocol`, `bibliographic-resource`,
  `provenance`, `usage-policy`, and their join tables): methods, literature, origins and rights.

Tables named `a-b`, such as `material-media` or `event-protocol`, link rows of `a` to rows of `b`
when one can have many of the other.

## What simplification is allowed

The conceptual model says implementations may simplify. For example, organism details can stay on
the occurrence when there is no reason to track the organism across occurrences. Use the fewest
tables the data need, and add a table only when the data have something for it.
