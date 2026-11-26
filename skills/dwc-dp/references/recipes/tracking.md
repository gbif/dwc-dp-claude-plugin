# Recipe: tracked individuals (GPS, Argos and other tags)

## When it applies

Animals carry a tag that records or transmits where they are: GPS, Argos (satellite Doppler),
geolocators, or radio and acoustic telemetry. The data are many locations of a few known
individuals. Most often they come from Movebank, as two files:

- **the locations:** one row per location, with `event-id`, `timestamp`, `location-lat` and
  `location-long`, the tag, the individual, and sensor-specific columns such as `argos:lc`,
  `gps:hdop` or `height-above-msl`;
- **the reference data:** one row per deployment (a tag on an animal), with the animal (taxon, sex,
  life stage), the tag (manufacturer, model), the deployment (on and off dates, attachment, duty
  cycle) and comments.

Movebank's attributes are defined in its Attribute Dictionary, with an IRI for each in the NERC
Vocabulary Server (http://vocab.nerc.ac.uk/collection/MVB). A Movebank data package's README lists
the ones it uses. Read it: it says which entity each attribute describes (event, individual,
deployment, tag), and that decides the table.

Re-sightings of marked individuals without a tag, such as rings, natural marks or camera traps,
use the same `organism` table. This recipe covers tags.

## Tables

| Table | What it holds (from the schema) |
|---|---|
| `event` | the study, one event per deployment, a tag-attachment event, and one event per location |
| `organism` | "A particular organism…": each tracked animal, with the animal ID as `organismID` |
| `occurrence` | "A dwc:Event that establishes the state of a dwc:Organism at a particular place and time": the animal at its tagging and at each location, all pointing to the organism (`organism_fk`, and `organismID`, which GBIF's indexing follows) |
| `identification` | the animal's name, *of* the organism (`organism_fk`), once per animal instead of once per location |
| `agent`, `event-agent-role` | the tag, as an agent of type machine (the schema counts machines as agents), and its role in the deployment |
| `event-assertion` | deployment attributes without a field: attachment type, duty cycle, manipulation, readout method, outlier filter |
| `organism-assertion` | traits of the animal without a field, such as Movebank's animal group |

Fill order (`dwcdp.py order`): event, organism, agent, identification, occurrence, then the
assertion and role tables.

## The events

1. **The study:** `eventCategory` `context`, `eventType` `Project`.
2. **A deployment per tag on an animal:** `context`, with `eventType` `Sensor` (GBIF's concept,
   labelled "Deployment"). Its date is the interval from deploy-on to deploy-off.
3. **The tag attachment:** the animal in hand or approached. It is an occurrence of the animal at
   the deploy-on place and date, with the life stage at the start of the deployment, which is how
   Movebank defines `animal-life-stage`.
4. **One event per location,** under its deployment, with Movebank's `event-id` as `eventID` and
   the timestamp in UTC (`2010-02-21T09:48:00Z`).

Each location event has one occurrence of the animal, with `occurrenceStatus` `detected` and
`organism_fk`. Put on it what holds at that moment: `sex` (GBIF indexes it on occurrences),
`behavior` if a sensor classified it. Don't copy the life stage onto later locations: it was
recorded for the start.

## Choices for the data holder

- **Which locations:**
  - Movebank files may hold raw fixes and **modelled** ones (`modelled` = TRUE: state-space
    models, interpolations, regular time steps). Modelled positions are estimates, not
    observations of the animal. Ask whether they stay out, or go in marked as estimates.
  - **Outliers** (`visible` = FALSE, or any `*-marked-outlier` = TRUE): usually left out. Ask, and
    keep the deployment's `outlier-comments`.
  - **Locations outside the deployment** (before deploy-on, after deploy-off): not of the animal.
    Leave them out, and count them for the data holder.
- **Thinning.** GPS can give millions of fixes. The bird-tracking example (gbif/dwc-dp-examples,
  with INBO's movepub) keeps the first fix per animal per hour, and records that in
  `dataGeneralizations` (for example "subsampled by hour: first of 12 record(s)"). Thinning is
  never a default: offer it when the volume is a problem, and use it only with their agreement.
- **Coordinate uncertainty.** Use the sensor's own estimate when there is one
  (`location-error-numerical`). Otherwise derive it only by a rule the data holder agrees to, and
  state the rule in `georeferenceProtocol`. For Argos, the location class has nominal accuracies
  for classes 3, 2 and 1 (under 250 m, 250–500 m and 500–1500 m), and none for 0, A and B. GPS
  HDOP is not a distance. Keep the class or HDOP in `georeferenceRemarks` either way.
- **Height and depth.** `height-above-msl` and `height-above-ellipsoid` are altitudes. Dive depth
  from a pressure sensor is a depth. Ask which DwC-DP depth or distance field they mean, and say
  which reference surface the field uses.
- **Sex values** such as Movebank's `u` (unknown): GBIF's Sex vocabulary has `Indeterminate`.
  Check its definition with `vocab Sex` and ask whether "unknown" means that, or leave it empty.
- **Other sensors** (acceleration, magnetometer, temperature): not locations. They are
  measurements, which could become occurrence assertions, but they can be very large. Ask whether
  they are published at all.

## Movebank attributes and where they go

`dwcdp.py suggest` recognises a Movebank export. When most of a table's columns are Movebank
attributes, it names each one with its id and entity, and gives its DwC-DP field from the crosswalk
in `crosswalks/movebank.json`. An attribute that isn't in the crosswalk gets the table for its
entity. The table below is the same crosswalk:

| Movebank attribute (entity) | DwC-DP |
|---|---|
| `event-id` (event) | `event.eventID` of the location event, and its `event_pk` |
| `timestamp` (event) | `event.eventDate`, in UTC, as ISO 8601 |
| `location-lat`, `location-long` (event) | `event.decimalLatitude`, `decimalLongitude`. Movebank defines them as WGS84, so `geodeticDatum` `WGS84` |
| `argos:lc`, `gps:hdop`, `location-error-numerical` (event) | `georeferenceRemarks`, and `coordinateUncertaintyInMeters` as agreed (above) |
| `modelled`, `visible`, `*-marked-outlier` (event) | which rows become occurrences (above) |
| `comments` (event) | `eventRemarks` |
| `individual-local-identifier`, `animal-id` (individual) | `organism.organismID` and `organism_pk` |
| `animal-taxon`, `individual-taxon-canonical-name` (individual) | `identification.scientificName`, of the organism |
| `animal-nickname` (individual) | `organism.organismName` |
| `animal-sex` (individual) | `occurrence.sex` |
| `animal-life-stage` (deployment) | `occurrence.lifeStage` of the tag attachment |
| `animal-group-id` (individual) | `organism-assertion` |
| `animal-death-comments` (individual) | `organism.causeOfDeath`, if it states one |
| `deployment-id` (deployment) | `event.eventID` of the deployment event |
| `deploy-on-date`, `deploy-off-date` (deployment) | the deployment's `eventDate` interval; deploy-on also on the attachment event |
| `deploy-on-latitude`, `deploy-on-longitude` (deployment) | the attachment event's coordinates |
| `attachment-type`, `duty-cycle`, `manipulation-type`, `tag-readout-method`, `outlier-comments` (deployment) | `event-assertion` on the deployment, with the MVB IRI as `assertionTypeIRI` |
| `tag-id`, `tag-manufacturer-name`, `tag-model` (tag) | an `agent` of type `machine`, and an `event-agent-role` (`recorded by`) on the deployment |
| `study-name` (study) | the study event, and the package's title |

An attribute not listed here: look it up in the README or the Attribute Dictionary, then
`find-term`. If nothing fits, it is an assertion on the table for its entity (event: the location
event; deployment: the deployment event; individual: the organism).

## Worked example: `tests/fixtures/tracking-argos/`

Published data, CC0: three of the 50 humpback whales in Movebank study 3030068329 (Andrews-Goff et
al. 2023, https://doi.org/10.5441/001/1.294). The three are an adult male, an adult of unknown sex,
and a calf. The tags are Argos (Wildlife Computers Spot 5). The file holds raw Argos fixes,
including three flagged outliers, and the paper's state-space model estimates.

- **Agreed:**
  - raw fixes without outliers (45 locations);
  - no thinning;
  - the uncertainty from the Argos location class.
- **The result:**
  - 52 events: the study, 3 deployments, 3 attachments and 45 locations;
  - 3 organisms, each with one identification and an animal group assertion;
  - 48 occurrences, all pointing to their organism;
  - 3 tags as agents;
  - one identification per whale, and for GBIF a copy based on each of its 48 occurrences;
  - 15 deployment assertions.
- **`validate` warns** that GBIF reads the life stage `Calf` as its concept `Juvenile`. That's the
  data holder's call: convert it, or keep their word.

## Pitfalls

- **One occurrence per location without `organism_fk`:** the track falls apart into unrelated
  records. Every occurrence of the animal points to its organism, with `organism_fk` and with the
  organism's `organismID` in `organismID`: GBIF's indexing links them by the identifier.
- **The name repeated on every occurrence:** names go in `identification`, once per organism. GBIF's
  indexing currently reads an occurrence's name only from an accepted identification based on that
  occurrence, not from its organism's. So for GBIF, add one per occurrence, copied from the
  organism's, with `identificationRemarks` saying so (SKILL.md, Stage 7). The example does this as
  its last step.
- **Local times:** Movebank timestamps are UTC. Write them with `Z`.
- **Deploy-on and deploy-off at 00:00:00 and 23:59:59:** these usually mark whole days. Ask before
  writing them as times.
- **Two animals on one tag, or one animal with two tags:** one deployment each. Key deployments by
  `deployment-id`, not by the tag.

## Sources

- DwC-DP 1.0 table schemas `organism`, `occurrence`, `identification`, `event`, `agent` and
  `event-agent-role` (the vendored copies).
- GBIF's EventType, Sex and LifeStage vocabularies (the pinned copies).
- The Movebank Attribute Dictionary, https://www.movebank.org/cms/movebank-content/movebank-attribute-dictionary,
  and its IRIs at http://vocab.nerc.ac.uk/collection/MVB.
- gbif/dwc-dp-examples `observation/bird-tracking` (Apache-2.0, written for 0.1) and INBO's
  movepub: the event hierarchy and hourly thinning, as patterns.
- Argos location classes: CLS, Argos User's Manual.
