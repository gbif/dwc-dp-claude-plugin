# Recipe: observations, interactions and camera traps

## When it applies

The data are organisms seen, heard, photographed or recorded, without specimens kept:

- **field notebooks and observation spreadsheets:** one row per organism seen, often with photos;
- **interactions:** a visitor on a flower, a predator with its prey, a parasite on its host. They are
  often unnamed: a host column, or `associatedTaxa`. `../interactions.md` covers how to spot and
  build them;
- **tracking:** animals with GPS, Argos or other tags have their own recipe, `tracking.md`;
- **camera traps:** deployments, images and the observations classified from them, often already
  as a Camtrap DP package (https://camtrap-dp.tdwg.org).

If the observations came from a planned survey with a method and targets, read `survey.md` as
well. A camera deployment can be a survey too: the schema gives "a camera trap deployment in a
rainforest to monitor large mammals" as an example of `survey`.

## Tables

| Table | What it holds (from the schema) |
|---|---|
| `event` | where and when. In DwC-DP 1.0 an occurrence has no date, time or place of its own: they come from its event (`occurrence.event_fk`, required) |
| `occurrence` | "A dwc:Event that establishes the state of a dwc:Organism at a particular place and time": what was seen, how many, sex, life stage, behaviour, and the name given |
| `organism-interaction` | "An interaction between two dwc:Organisms during a dwc:Event", between a subject occurrence and a related one |
| `media` | "A digital or physical media resource": the photo, sound or video |
| `occurrence-media`, `event-media`, `organism-interaction-media` | which occurrence, event or interaction a media item shows |
| `agent`, `media-agent-role`, `event-agent-role` | people with roles, such as the photographer or who set up a camera |
| `occurrence-assertion`, `event-assertion` | facts the tables have no field for, such as how an image was classified or how high a camera hung |
| `organism` | an individual seen more than once (a tagged or named animal), with `occurrence.organism_fk` |

`dwcdp.py order` gives the order for the tables used. Both worked examples need event before
occurrence, occurrence before interaction, and media before the `*-media` tables.

## Keys

- **Observations:** their observation or record number as `occurrenceID`. For a platform, that is
  the platform's identifier (iNaturalist's observation URL, for example).
- **Events:**
  - when an observation has its own time and place, its event can use the observation's number;
  - when several observations share a moment (a flower and its visitor), use one key for that
    moment, agreed with them;
  - for a camera trap, the deployment ID for the deployment, and the sequence (`eventID` in
    Camtrap DP) for each sequence.
- **Media:** their media ID, or the file's URL when that is all they have and it is stable.
- **Interactions:** usually none in the data. Combine subject and related occurrence (`O2>O1`).
- **Agents:** an ORCID or other identifier as `agentID` when they have one. Otherwise a key made
  from the name, and say so.

## Mapping, step by step

### Field notebook with interactions: `tests/fixtures/observations-pollinators/`

Made-up pollinator observations: five rows (two flowers, their two visitors and one bumblebee
flying), three photos, and who took them.

1. **Events:** one per place and moment. The rows with the same date, time and coordinates were
   seen together, so a flower and its visitor share an event.
   - `eventCategory` `occurrence`.
   - `geodeticDatum` `not recorded`, because the notebook doesn't say. That is the value the
     schema's notes give for this case.
2. **Occurrences:** one per row, with `occurrenceStatus` `detected` (required), the count, sex and
   behaviour. The name of each is an `identification` based on it.
3. **Interactions:** one per visitor that names the flower it was on.
   - The visitor is the subject. The schema's notes: "with the actor as the subject dwc:Occurrence
     and the acted-upon as the related dwc:Occurrence".
   - `organismInteractionType` `visited flower of`, one of the schema's examples, and
     `relatedOrganismPart` `flower`.
4. **Photos:**
   - **Photographers:** an `agent` each.
   - **The photos:** a `media` row each, with `mediaType` `StillImage`, the URL as `accessURI` and
     the licence.
   - **Credit:** `media-agent-role` with `agentRole` `creator`.
   - **Subject:** `occurrence-media` for the occurrence each photo shows.

### Camera traps from Camtrap DP: `tests/fixtures/observations-camtrap/`

The example dataset of Camtrap DP 1.0.2, unchanged: a sample of INBO's MICA muskrat and coypu
camera traps (data CC0, images CC BY 4.0). It has:
- four deployments;
- 423 images, 60 of them not public;
- 549 observations at two levels: 36 classify a whole sequence of images (`observationLevel`
  `event`) and 513 a single image (`media`). 22 were made by a machine model.

1. **Choose what to publish.**
   - **One level only.** Camtrap DP can classify the same animals per sequence and per image.
     Publishing both counts them twice. The example publishes the event-level observations and
     uses the media-level ones only to link images to sequences. A package with only media-level
     observations publishes those.
   - **Only animals.** Blank, unknown, unclassified, vehicle and human observations report no
     organism.
   - **People's privacy.** Images of people (here the non-public ones) stay out, as do the images of
     sequences that aren't published.
   - All three are the data holder's choices.
2. **Deployments:** an event each, with:
   - `eventDate` from `deploymentStart` to `deploymentEnd`;
   - the location, with `geodeticDatum` `EPSG:4326` (Camtrap DP gives coordinates in WGS84) and
     `coordinateUncertainty` in metres;
   - `eventCategory` `context` and `eventType` `Sensor`, GBIF's concept whose labels include
     "Deployment";
   - `deploymentComments` as `eventRemarks`.
3. **Cameras and people:**
   - Each camera is an `agent` with `agentType` `camera` (a schema example) and the role
     `recorded by` in its deployment, as a tracking tag is in `tracking.md`.
   - Whoever set the camera up is an agent with the role `setupBy`, when named. One is anonymized
     in the data (`anonymized:3eb30aa`) and stays as written.
4. **Camera set-up:** delay, height, depth, tilt, heading, detection distance, bait, feature type,
   groups and tags are `event-assertion` rows, with the units Camtrap DP defines for them (s, m,
   degrees).
5. **Sequences:** an event each, within its deployment (`parentEvent_fk`), from the first to the
   last image (`eventStart`/`eventEnd`), with `eventCategory` `occurrence`.
6. **Observations:** an occurrence each, with the count, life stage, sex, behaviour and comments.
   - The name is an `identification` based on the occurrence, with `classifiedBy` as
     `identifiedBy` (a person, or the model's name) and `classificationTimestamp` as
     `dateIdentified`.
   - `taxonID`, `taxonRank` and the English vernacular name come from the package's `taxonomic`
     list in `datapackage.json`, which `read_json` reads directly.
   - Classification method and probability are `occurrence-assertion` rows.
7. **Images:** the public images of the published sequences go in `media`, with the package's media
   licence. They are linked to their sequence with `event-media`, using the media-level
   observations. Without media-level observations, link an image to the sequence of the same
   deployment whose `eventStart` to `eventEnd` includes its timestamp. Compare the times as
   `TIMESTAMPTZ`, not as text, since offsets differ (`+02:00` against `Z`).

## Choices the data holder makes

- **What one event is.**
  - Each observation, each moment shared by several observations, a site visit, or a camera
    sequence.
  - An occurrence's time and place are its event's. So two observations at different times can't
    share an event without losing their times.
- **`eventCategory`** is required, with examples and no list (see `survey.md`). The examples use
  `occurrence` for the moment of an observation and `context` for a deployment. Let them choose.
- **`eventType`:** GBIF's draft vocabulary has `Observation`, `Sensor`, `SiteVisit` and others
  (`dwcdp.py vocab event.eventType`).
- **Interactions:**
  - Which organism is the subject: the actor, by the schema's notes.
  - The interaction type: the schema recommends a controlled vocabulary and gives examples
    (`visited flower of`, `pollinated by`, `parasitoid of`, `mated with`, `was attached to`), no
    list.
  - Both directions may be written, "as distinct OrganismInteractions", but one is enough.
  - An interaction with more than two organisms is several pairs.
  - The other organism may be outside the package: `externalRelatedOccurrenceID` and
    `externalRelatedOccurrenceSource`.
- **Which records to publish.** Blank camera sequences, people, vehicles and machine
  classifications below a threshold are theirs to keep out or put in. Images of people are
  usually kept out (Camtrap DP marks them `filePublic` false).
- **Names** go in `identification`, one per name, based on the occurrence (`occurrence_fk`), or
  on a particular image (`media_fk`) when that is what was identified.
  - The occurrence's own name fields (`scientificName`, `identifiedBy`, `dateIdentified`, ...) stay
    empty, which is the maintainers' rule. `validate` warns about a name on an occurrence.
  - Several determinations of one observation are several identifications, with
    `isAcceptedIdentification` on the current one.
- **Machine classifications.** Who classified is the identification's `identifiedBy`, whether a
  person or a model with its version. The method and probability have no field, so the example
  keeps them as occurrence assertions.
- **Media rights.** `license` on the media, or `usage-policy` and `media-usage-policy` when rights
  are shared by many items. Use what they state; don't assume a licence.
- **Who took the photo.** The media table has no creator field. `media-agent-role` with a role
  such as `creator` holds it. The role vocabulary is theirs to choose: the schema only recommends
  "a controlled vocabulary for the roles appropriate to the class of resource".

## Pitfalls

- **Two observations at different times on one event:** the later one gets the earlier one's
  time. `validate` can't see it. Check that rows grouped into one event really share their
  moment.
- **The visitor and the flower swapped:** `validate` can't see it either. Read a few interactions
  aloud: "O2 (Bombus lapidarius) visited flower of O1 (Knautia arvensis)".
- **An interaction pointing to an observation that isn't published,** such as a flower photographed
  by someone else: the link fails in `validate`. Use the external identifier fields instead.
- **The same animals counted twice:** Camtrap DP observations at both `event` and `media` level
  become two occurrences for one animal. Publish one level.
- **Images of people, or private files,** published by accident: filter on Camtrap DP's
  `observationType` and `filePublic` first, as the example does.
- **Times compared as text:** sequences and images from deployments with different time zone
  offsets don't match. Cast to `TIMESTAMPTZ`, as the example does.
- **Sex or life stage values outside GBIF's vocabularies:** `validate` warns. Camtrap DP's `adult`,
  `female` and `male` are concepts there.

## Sources

- DwC-DP 1.0 table schemas `occurrence`, `organism-interaction`, `media`, `occurrence-media`,
  `event-media`, `media-agent-role`, `event-agent-role`, `occurrence-assertion`, `event-assertion`
  and `event` (the vendored copies), including the notes quoted above.
- Darwin Core conceptual model, https://dwc.tdwg.org/cm/, sections 2.3 (occurrence, organism,
  organism interaction) and 2.8 (media).
- Camtrap DP 1.0.2 table schemas (`deployments`, `media`, `observations`) at
  https://github.com/tdwg/camtrap-dp.
- gbif/dwc-dp-examples at `a9994e8f72` (2026-10-21), from before 1.0, read for how they split the
  data:
  - **`organism_interaction/inaturalist`:** an event per observation under a project event,
    interactions of type `visited flower of` with the visitor as subject, and photos in
    `event-media` and `occurrence-media`;
  - **`organism_interaction/conabio-bees`:** looked at only for its tables (event, material,
    occurrence, organism-interaction, organism-interaction-assertion);
  - **`observation/bird-tracking`:** looked at only for its tables and events (a tag deployment
    event with the tag attachment and GPS positions as child events; occurrence,
    occurrence-assertion).
- GBIF's `eventType`, `LifeStage` and `Sex` vocabularies (the pinned copies).
