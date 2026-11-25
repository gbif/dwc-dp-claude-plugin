# Recipe: surveys and sampling events

## When it applies

The data come from planned visits that looked for something with a method: point counts,
transects, trap nights, plots, electrofishing passes, camera deployments. The files usually are:

- a list of sites, with coordinates and habitat;
- a list of visits or samples, with date, observer and effort;
- a table of counts per visit and species, often with zeros;
- a methods text.

If the records are incidental observations with no method behind them, this recipe is not the
one; there is no survey to describe.

## Tables

| Table | What it holds (from the schema) |
|---|---|
| `event` | "an action, a process, or a set of circumstances occurring at some place during some interval of time" (conceptual model 2.1); one row per project, visit, sample or other level |
| `survey` | "A dwc:Event intentionally designed to characterize a defined biotic target or domain in such a way that the resulting dwc:Occurrences can be interpreted collectively…" Its `event_fk` (required) points to the event it describes |
| `survey-target` | "One or more scopes that describe a target for dwc:Occurrences in an eco:Survey" |
| `survey-target-descriptor` | "A combination of a survey target value and a survey target type for a given eco:SurveyTarget", such as `taxon: Aves`, include or exclude |
| `survey-survey-target` | "An eco:SurveyTarget used for an eco:Survey": the link between surveys and targets, many to many |
| `occurrence` | what was recorded on each visit or sample, with `event_fk` and, for what the target covers, `surveyTarget_fk` ("occurrence satisfied survey-target") |

`dwcdp.py order` puts them in this order: event, survey-target, occurrence, survey,
survey-target-descriptor, survey-survey-target.

Add `protocol` (for `samplingProtocol_fk`), `agent` (for observers with identifiers) or
`event-assertion` (for measurements such as water temperature) only when the data have something
for them.

## Keys

- **Events:** the data holder's visit or sample code as `eventID`, and as `event_pk` when it is
  unique. The project or larger levels usually have a code or a name to use. If not, make one with
  them, and say so.
- **Surveys:** usually none in the data. A prefix on the event's key (`survey:V1`) keeps them
  readable.
- **Targets:** a short name agreed with them (`birds-except-gulls`).
- **Occurrences:** their record number if they have one; otherwise the visit and the species
  (`V1:Fringilla coelebs`), which is unique when each species is counted once per visit.

## Mapping, step by step

There are two worked examples. The first is `tests/fixtures/survey-point-counts/`: made-up point counts with two sites,
three visits, a count table with zeros, a gull and a hare, and a methods text (`protocol.txt`).
Its `mapping.sql` is the full mapping.

1. **The project event:**
   - the parent of every visit, with dates spanning them (`min(date) || '/' || max(date)`);
   - `eventCategory` `context`, `eventType` `Project`.
2. **One event per visit:**
   - `parentEvent_fk` set to the project;
   - the place taken from the site (locality, habitat, coordinates);
   - `eventCategory` `survey`, `eventType` `SiteVisit`;
   - the observer as `recordedBy`.
3. **The target:** one `survey-target` row with its description, and `isSurveyTargetFullyReported`
   (required). Two descriptors: `taxon Aves include` and `taxon Larus exclude`.
4. **One survey per visit:**
   - `event_fk` pointing to the visit;
   - the method as `samplingProtocol`;
   - effort as `samplingEffortValue` 10 with `samplingEffortUnit` minutes;
   - `isAbundanceReported`, `isAbsenceReported` and `hasNonTargetTaxa` / `nonTargetTaxa`, from the
     data and the methods text.
5. **Links:** one `survey-survey-target` row per survey, to the shared target.
6. **Occurrences:** one per row of the count table:
   - `occurrenceStatus` `notDetected` for a count of 0 and `detected` otherwise (the field is
     required);
   - the count as `organismQuantity`, with `organismQuantityType` `individuals`;
   - `surveyTarget_fk` for the species the target covers, and empty for the gull and the hare;
   - the note as `occurrenceRemarks`.

7. **Weather:** the weather and wind force of each visit have no field, so they are
   `event-assertion` rows about the visit, with the unit (`Beaufort`) from the column name
   (`references/assertions.md`).

`dwcdp.py diagram` shows the result, and `validate` and `check` pass on it.

### Trap catches kept as material: `tests/fixtures/survey-malaise-bulk/`

Made up:
- two two-week catches of a Malaise trap, kept in ethanol;
- two pinned vouchers sorted out of them;
- a COI metabarcoding run on DNA extracted from each catch's ethanol.

This joins the survey to the specimens and eDNA recipes (`specimens.md`, `edna.md`), whose details
apply.

1. **Events and surveys:** each catch is an event, from setting to emptying the trap. Each event
   has a survey, with:
   - `samplingProtocol` `Malaise trap`;
   - the effort in trap-days, computed from the dates with the data holder's agreement;
   - `hasMaterialSamples` and `materialSampleTypes`, which say material was kept;
   - `hasVouchers`.
2. **The catch** is material collected during its event (`collectionEvent_fk`), with its
   preservation and disposition.
3. **Vouchers:** each is material that is part of its catch (`isPartOfMaterialEntity_fk`). Each
   is also the evidence for an occurrence in the catch's event, with its own identification.
4. **Size fractions and counted groups:** each catch was sieved into a large and a small fraction,
   and the taxon groups in each were counted, some as numbers and some as `few`, `some` or `many`.
   - A fraction is material that is part of its catch (`isPartOfMaterialEntity_fk`).
   - A counted group is material that is part of its fraction. Its count is in `objectQuantity`,
     as written, with `individuals` in `objectQuantityType`. The schema's own examples include
     `many` with `individuals`.
   - Its name is an identification of that material, at the rank the sorter used, such as an
     order.
5. **The extract** is derived from the catch. The COI analyses point to it, as in `edna.md`.

## Choices the data holder makes

- **The levels of events.**
  - A child event lies within its parent in space and time, and has one parent (conceptual model
    2.1).
  - Typical levels are a project, a site visit and a sample. NEON-fish nests five: project, site,
    reach, reach sampling and pass. Use the levels their design has.
  - A site is a place, not an event. Its coordinates and habitat go on the events at it, unless
    they want the site itself as a level that groups visits over time, as NEON-fish does.
- **`eventCategory` for each level.**
  - It is required. The schema recommends "a limited, tightly controlled vocabulary", gives
    examples (`survey`, `occurrence`, `material collection`, `context` and others), and no list.
    GBIF has no vocabulary for it.
  - Propose the examples and let them choose. The conceptual model uses `context` for an event
    that frames others.
- **`eventType`.** GBIF reads it with its `eventType` vocabulary, a draft:
  - Project, Expedition, Survey, SubSurvey, Inventory, Bioblitz, SiteVisit, Sample, SubSample,
    Sensor, NucleotideAnalysis and Observation;
  - `dwcdp.py vocab event.eventType` lists them.
  - Their own word is allowed; `validate` then warns that GBIF won't interpret it.
- **Which events get a survey row.**
  - Every survey points to one event. Put it on the level at which the method, the effort and
    the targets are known: usually each visit or sample.
  - When effort is only known in total, one survey on the project may be what the data support.
  - The examples differ: NEON-fish has a survey for every event, broke-west-fish for 250 of
    376.
- **Targets.**
  - A target is a scope built from include and exclude descriptors, such as "all flying adult
    Aves except Passeriformes" (notes of `includeOrExclude`).
  - One target can serve many surveys through `survey-survey-target`. Use separate targets when
    visits looked for different things.
- **Absences.** They come in three ways:
  - **Rows:** `notDetected` occurrences for what they recorded as zero or absent;
  - **A fully reported target:** `isSurveyTargetFullyReported` true says every count matching the
    target was reported. The schema: "this enables inference of absence of detection for everything
    in that eco:SurveyTarget that is included but that does not appear in the counts";
  - **Both,** as in the example.

  Write `notDetected` rows only for records they have; never generate rows for species they didn't
  list. Set `isSurveyTargetFullyReported` true only when their method says all counts were
  reported, and false otherwise. The field is required, so don't leave it out.
- **Records outside the target** (bycatch, incidental species): occurrences without
  `surveyTarget_fk`. On the survey:
  - `hasNonTargetTaxa` and `nonTargetTaxa` say they occurred. Build `nonTargetTaxa` only from
    names they trust: a weak DNA match or a contaminant (`edna.md`, "Names from a sequence
    matching tool") is not a record of bycatch. Ask which names go in;
  - `areNonTargetTaxaFullyReported` says whether all were reported. Leave it empty unless their
    method says.
- **Effort and its unit.**
  - `samplingEffortValue` needs `samplingEffortUnit` (notes of `samplingEffortValue`).
  - "For compilations it is recommend not to infer effort": only use effort they recorded.
- **Counts.**
  - `organismQuantity` needs `organismQuantityType`.
  - Whether a 0 stays in `organismQuantity` next to `notDetected` is their choice; the example
    keeps it.
- **Material from a survey.** When something physical was kept (trap catches, plankton samples,
  soil cores), it is material collected during the survey's event:
  - `hasMaterialSamples` and `materialSampleTypes` on the survey say so, and `hasVouchers` and
    `voucherInstitutions` say whether specimens were kept and where;
  - ask which institution and collection hold the catches and vouchers, for `institutionCode`,
    `collectionCode` and their IDs on the material (SKILL.md, Stage 3);
  - specimens sorted out of a bulk sample are part of it, or derived from it. That is their
    choice, as in `specimens.md`. The same goes for fractions: a sieved fraction is a part of the
    catch, while an extract, a homogenate or anything else made from it is derived;
  - groups counted in a sample can be material, as in the example, or occurrences of each group at
    the sample's event (with `organismQuantity`, and based on the sample). Material keeps the
    count with the fraction it came from. Occurrences give one record per group and sample. Show
    them both and let them choose;
  - DNA from it follows `edna.md`.
- **Fields the methods text doesn't settle,** such as `taxonCompletenessReported`: leave them
  empty, and tell them which.

## Pitfalls

- **An occurrence attached to the project instead of the visit.** `validate` can't see it, since
  the link resolves. Check with `sql` that occurrences point to the lowest level.
- **A survey without `event_fk`:** "N rows have no event_fk, which is required".
- **A target without `isSurveyTargetFullyReported`**, or a descriptor without `includeOrExclude`:
  both are required.
- **Occurrences without `occurrenceStatus`:** required in 1.0.
- **Repeated species on a visit,** such as two rows for one species from two observers: the
  occurrence key `visit:species` is then not unique, and `validate` reports a duplicate key. Ask
  how they want them told apart, or whether the rows should be one.
- **Status values outside GBIF's vocabulary,** such as `present` or `absent` (deprecated in
  favour of `detected` and `notDetected`): `validate` warns, and names the replacement.

## Sources

- DwC-DP 1.0 table schemas `survey`, `survey-target`, `survey-target-descriptor`,
  `survey-survey-target`, `event` and `occurrence` (the vendored copies), including the field notes
  quoted above.
- Darwin Core conceptual model, https://dwc.tdwg.org/cm/, sections 2.1 (events and hierarchies) and
  2.2 (surveys).
- gbif/dwc-dp-examples at `a9994e8f72` (2026-10-21), all from before 1.0, read for how they split
  the data:
  - **`survey/NEON-fish`:** the five-level event hierarchy and a survey for each event;
  - **`survey/broke-west-fish`:** one `survey_target` row per survey with type and value
    columns. In 1.0 these became `survey-target`, `survey-target-descriptor` and
    `survey-survey-target`;
  - **`survey/insektmobilen`:** output only, with `survey_pk`/`event_fk` columns; its mapping
    script is a draft.
- GBIF's `eventType` and `OccurrenceStatus` vocabularies (the pinned copies).
