# Recipe: dated material and geological time

## When it applies

Any dataset in which material, or the organisms it is evidence of, has an age or a place in
geological time. DNA is not needed. For example:

- **fossil collections** with formation, member, bed, stage or biozone on the label;
- **subfossil and archaeological finds** from excavated layers, with radiocarbon or other dates;
- **cores and sequences**: lake and marine sediments, peat or ice, with depths and an age-depth
  model, and sometimes pollen, macrofossils or sedimentary ancient DNA (sedaDNA);
- **rock and mineral samples** collected with the fossils.

Typical files: a specimen or sample sheet with stratigraphy or depths (often only inside sample
IDs), a table of dates from the dating lab, and the paper or report that describes the dating.

## Tables

| Table | What it holds (from the schema) |
|---|---|
| `event` | the collecting: an excavation of a layer, a visit to an outcrop, a coring. Below it, a subsample, if needed (see ages) |
| `material` | the specimens, samples and cores, and what was taken from them: parts (`isPartOfMaterialEntity_fk`) and subsamples (`derivedFromMaterialEntity_fk`) |
| `occurrence`, `identification` | the organisms the specimens are evidence of, and their names, as in `specimens.md` |
| `chronometric-age` | "An approximation of temporal position … that is supported via evidence". Its notes: "The age of a dwc:MaterialEntity and how this age is known" |
| `protocol` | how an age is known (dating method, age-depth model), its calibration, and mineralogical analyses |
| `geological-context` | "A set of geological designations, such as stratigraphy": eons to stages, biozones, group, formation, member, bed |
| `material-geological-context` | which material lies within which geological context |
| `geological-material` | "A dwc:MaterialEntity that is geological in nature": mineral and lithology names, chemistry, mineralogical analyses |
| `material-assertion` | measurements of the material without a field, such as depth in a core |
| `bibliographic-resource` and the `*-reference` tables | the publications behind the dating or the stratigraphy |

For sedaDNA, add the eDNA tables (`edna.md`).

## Ages belong to an event

`chronometric-age.event_fk` is required, and the table has no link to the material an age applies
to. It does link to the material that was *dated* (`materialDated_fk`), which may be something else,
such as charcoal from the same layer. So an age is an age of an event, and of everything collected
in it:

- **A layer excavated, or an outcrop bed visited:** every find collected in that event shares its
  ages. Two dates of one layer are two ages of one event.
- **A find that needs an age of its own:** give it its own event, such as a subsampling event under
  the excavation or coring event (`parentEvent_fk`, `eventType` `SubSample`, a GBIF concept). The
  sedaDNA example does this for each slice of the core.

Ask how finely their ages apply: to a layer, a sample, or a single specimen. That decides the
events.

## Writing an age

One `chronometric-age` row per age:

- **`earliestChronometricAge` and `latestChronometricAge`:** the oldest and youngest ages in
  years, such as a calibrated range. For a single model age, both are the same. The schema says
  each "must have an associated" reference system.
- **The reference systems:** as the data state them, for example `cal yr BP`. Never assume
  "BP" means calibrated.
- **`uncalibratedChronometricAge`:** the measurement before calibration, for example a radiocarbon
  age `10450 ± 60 14C yr BP`.
- **`chronometricAgeConversionProtocol` and its `_fk`:** the calibration, such as a curve.
- **`chronometricAgeProtocol` and its `_fk`:** how the age is known. For example AMS radiocarbon
  dating, OSL or an age-depth model, as a `protocol` row with `protocolType` `chronometric age`
  (the calibration's is `chronometric age conversion`; both are schema examples).
- **`verbatimChronometricAge`:** the age as reported.
- **`materialDated`, `materialDated_fk` and `materialDatedID`:** what was dated. Use the `_fk` only
  when that material is in the package.
- **`materialDatedRelationship`:** how the dated material relates to the find, in the data
  holder's words (`same layer`), when it isn't the find itself.
- **`chronometricAgeUncertaintyInYears`:** an uncertainty of the earliest and latest ages, only
  when the data give one. A radiocarbon age's "±" is about the uncalibrated age, not this.
- **`chronometricAgeID`:** the lab number, if there is one.

## Geological time and stratigraphy

The chronostratigraphic fields (`earliestEonOrLowestEonothem` … `latestAgeOrHighestStage`) are read
with GBIF's GeoTime vocabulary (`dwcdp.py vocab GeoTime`), which has terms such as `Holocene`,
`Pleistocene`, `Maastrichtian` and `UpperCretaceous`. The lithostratigraphic fields (`group`,
`formation`, `member`, `bed`) and biozones are free text.

- **Recorded in the data:** formation, member, stage and so on go in as they are. Make one
  `geological-context` row per distinct combination, and link each find with
  `material-geological-context`. A find from an unnamed layer gets no context.
- **Not recorded:** an epoch or stage may be derived from an age only by a rule the data holder
  agrees to. For example, the Holocene began 11,700 years before AD 2000, which is
  11,650 cal yr BP. Show them the rule and the ages near the boundary. An age range that spans
  the boundary gets `earliest…` and `latest…` values that differ, or no context.

## Geological material

Use `geological-material` for rock, sediment and mineral samples whose mineralogy or lithology is
recorded. It is a `material` row with more detail (`materialEntity_fk`, "is a"):

- `geologicalMaterialNames` with `geologicalMaterialNameTypes`, as lists separated by ` | `;
- `mineralSequence`;
- `measuredChemistry` and its source;
- `mineralogicalAnalysisProtocol` and its `_fk`, the analysis that was used.

A fossil is `material` (`materialEntityCategory` `fossilized`), not geological material. Lake
sediment with only an age and DNA doesn't need this table.

## Depth in a core

`material` has no depth field. The event's depth fields (`minimumDepthInMeters` and so on) are
depths below the water or ground surface, not depths in a core. So depth in a core is a
`material-assertion` (`depth in core`, in cm), with the data holder's agreement.

Depths are often only in sample IDs (`PG1341-11_1783-1883cm_37-38cm`). Read them out with
`regexp_extract`, check the pattern against every ID, and say how a depth was computed (section top
plus depth in section). When two sources give the depth, check that they agree.

## Worked examples

### Fossils and subfossils, no DNA: `tests/fixtures/specimens-fossils/`

The data are made up:
- two subfossil bones from a cave layer;
- two Cretaceous fossils with formation, member and stage on their labels;
- two radiocarbon dates of the cave layer, one of a bone in the collection and one of charcoal
  that isn't;
- a rock sample from the cliff, with lithology and minerals from an X-ray diffraction analysis.

1. **Events and finds:** one collecting event per field number, and the specimens as material with
   their occurrences and identifications (`specimens.md`).
2. **Stratigraphy:** one `geological-context` with the recorded formation, member and stage
   (`Maastrichtian`). The fossils and the rock sample are linked to it. The cave finds get none,
   since none is recorded.
3. **Ages:** both dates are ages of the layer's event:
   - the calibrated range goes in the earliest and latest fields (`cal yr BP`);
   - the radiocarbon age goes in `uncalibratedChronometricAge`;
   - the dating method and the calibration curve are `protocol` rows;
   - `materialDated` says what was dated, with `materialDated_fk` for the bone in the collection.
4. **Rock sample:** a `material` row (`non-biological`) and a `geological-material` row with its
   names and analysis.

### A dated lake core with sedaDNA: `tests/fixtures/edna-sediment-core/`

Published data, CC0: Lake Lama, core PG1341, from von Hippel et al. (2022). The example uses four
depth slices, two Holocene and two Pleistocene, with ITS1 for fungi and trnL for plants.

1. **Events:** the coring event (1997, with the lake's coordinates and `georeferenceRemarks` saying
   the core position isn't given), and one `SubSample` event per slice, since each slice has its
   own age. The slice events have no date, since none is recorded.
2. **Material:** the core (`materialEntityType` `Core`, a schema example), its sections (part of the
   core), the slices (derived from their section and collected during their own event), and the
   DNA extracts (derived from their slice).
3. **Depth:** `material-assertion` rows, computed from the trnL IDs.
4. **Ages:** one per slice from the age-depth model, which is a `protocol` row cited to the paper.
5. **Epochs:** `Holocene` or `Pleistocene` by the agreed rule.
6. **DNA:** as in `edna.md`, with each analysis pointing to its slice's event and extract.

## Pitfalls

- **One find or extract with two ages** in different sheets. In the Lake Lama source data,
  extract ELS122 is 11,317 cal yr BP in one sheet and 13,209 in the other, either side of the
  Holocene boundary. Look for these with `sql` before mapping (`GROUP BY` the find,
  `count(DISTINCT age)`), and ask which is right.
- **"BP" without "cal":** an uncalibrated radiocarbon age goes in `uncalibratedChronometricAge`,
  not in the earliest and latest fields.
- **Earliest and latest swapped:** earliest is the oldest, so the larger number of years before
  present.
- **A stage written as an epoch** or the other way round: put each name in the field of its rank,
  and check it with `vocab GeoTime`.
- **Totals from a cut table** (sedaDNA): `processedTotalReadCount` is a replicate's total over all
  OTUs, not over the ones kept.

## Sources

- DwC-DP 1.0 table schemas `chronometric-age`, `geological-context`, `material-geological-context`,
  `geological-material`, `material`, `protocol` and `event` (the vendored copies): definitions,
  notes and examples.
- GBIF's GeoTime vocabulary (the pinned copy), and gbif/pipelines `vocabularyConfig` for the
  fields that use it.
- The base of the Holocene: Walker et al. (2009), Journal of Quaternary Science 24: 3-17,
  https://doi.org/10.1002/jqs.1227 (11,700 calendar years b2k).
- von Hippel et al. (2022), https://doi.org/10.1016/j.quascirev.2022.107758, and the data on Dryad,
  https://doi.org/10.5061/dryad.05qfttf3x.
