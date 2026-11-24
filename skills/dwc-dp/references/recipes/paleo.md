# Recipe: cores, dated material and geological time

## When it applies

The material has an age or a place in geological time: sediment or ice cores, peat sequences,
fossils, archaeological or zooarchaeological remains, subfossil bones. Typical files:

- a sample sheet with depths (often only inside the sample IDs), ages and the lab IDs;
- an age-depth model, or dating results (radiocarbon, OSL, tephra);
- for sedimentary ancient DNA (sedaDNA), OTU tables and taxonomy per marker, as in `edna.md`;
- the paper that describes the dating.

## Tables

| Table | What it holds (from the schema) |
|---|---|
| `event` | the coring or excavation, and below it one event per subsample |
| `material` | the core or find, and what was taken from it: sections (`isPartOfMaterialEntity_fk`, "part of"), slices and extracts (`derivedFromMaterialEntity_fk`, "derived from") |
| `chronometric-age` | "An approximation of temporal position … that is supported via evidence". Its notes: "The age of a dwc:MaterialEntity and how this age is known". `event_fk` is required |
| `protocol` | how the age is known: an age-depth model, a calibration, a dating assay |
| `geological-context` | "A set of geological designations, such as stratigraphy": epochs, stages, formations, biozones |
| `material-geological-context` | which material lies within which geological context |
| `material-assertion` | depth in the core, and other measurements of the material |
| `bibliographic-resource`, `protocol-reference`, `molecular-protocol-reference` | the publication that describes the methods |
| eDNA tables | for sedaDNA: `molecular-protocol`, `nucleotide-sequence`, `nucleotide-analysis`, `identification` (`edna.md`) |

`geological-material` ("A dwc:MaterialEntity that is geological in nature") holds mineral names,
chemistry and mineralogical analyses. Use it when the data have those. Lake sediment with only
DNA and an age doesn't need it.

## Ages

One `chronometric-age` row per dated piece of material:

- **`materialDated_fk`:** the material dated, such as the slice.
- **`earliestChronometricAge` and `latestChronometricAge`:** the age in years. For a single
  model age both are the same. The schema says each "must have an associated" reference system.
- **The reference systems:** as the data state them, for example `cal yr BP`. Never assume
  "BP" means calibrated.
- **`verbatimChronometricAge`:** the age as written.
- **`chronometricAgeProtocol` and `chronometricAgeProtocol_fk`:** how it is known. An age-depth
  model is a `protocol` row with `protocolType` `chronometric age` (a schema example), cited to
  its paper.
- **`uncalibratedChronometricAge` and `chronometricAgeConversionProtocol`:** a radiocarbon age
  before calibration, and the calibration curve, when the data have them.
- **`chronometricAgeUncertaintyInYears`:** only when the data give it.
- **`event_fk`:** required, but the schema doesn't say which event. The worked example gives
  each slice its own subsampling event under the coring event (`eventType` `SubSample`, a GBIF
  concept). The slice's age and its DNA analyses point to that event, so each slice has its own
  place in the event tree. Pointing every age to the coring event is the alternative. Ask which
  they want.

## Depth

`material` has no depth field. The event's depth fields (`minimumDepthInMeters` and so on) are
depths below the water or ground surface, not depths in a core. So depth in a core is a
`material-assertion` (`depth in core`, in cm), with the agreement of the data holder.

Depths are often only in sample IDs (`PG1341-11_1783-1883cm_37-38cm`). Read them out with
`regexp_extract`, check the pattern against every ID, and say how a depth was computed (section top
plus depth in section). When two sources give the depth, check that they agree.

## Geological time

`earliestEpochOrLowestSeries` and the other chronostratigraphic fields are read with GBIF's GeoTime
vocabulary (`dwcdp.py vocab GeoTime`): `Holocene`, `Pleistocene`, `Quaternary` and so on.

- **Stated in the data:** an epoch, stage or formation goes in as it is.
- **Not stated:** an epoch can be derived from the age only by a rule the data holder agrees to.
  For example, the Holocene began 11,700 years before AD 2000, which is 11,650 cal yr BP. Show
  them the rule and the ages near the boundary. An age whose uncertainty spans the boundary gets
  `earliest…` and `latest…` epochs that differ, or no context.
- Make one `geological-context` row per distinct context, and link material to it with
  `material-geological-context`.

## Worked example: `tests/fixtures/edna-sediment-core/`

Published data, CC0: sedaDNA from Lake Lama, core PG1341, from von Hippel et al. (2022). The
example uses four depth slices of the core, two Holocene and two Pleistocene, with ITS1 for fungi
and trnL for plants (several PCR replicates each, in more than one sequencing run).

1. **Events:** the coring event (1997, the lake's coordinates, with `georeferenceRemarks` saying the
   core position isn't given), and one `SubSample` event per slice, with no date, since the date
   isn't recorded.
2. **Material:**
   - the core (`materialEntityType` `Core`, a schema example);
   - its sections, part of the core;
   - the slices, derived from their section and collected during their subsampling event;
   - the DNA extracts, derived from their slice.
3. **Depth:** `material-assertion` rows for sections and slices, computed from the trnL IDs.
4. **Ages:** one `chronometric-age` per slice from the age-depth model, a `protocol` row for the
   model, and the paper as a `bibliographic-resource`.
5. **Epochs:** `Holocene` or `Pleistocene` by the agreed rule, through
   `material-geological-context`.
6. **DNA:** as in `edna.md`. Each analysis has its PCR replicate in its key, points to the slice's
   event and the extract, and has the replicate's total over all OTUs as
   `processedTotalReadCount`.

## Pitfalls

- **One extract with two ages** in different sheets. In the source data, ELS122 is
  11,317 cal yr BP in the fungal sheet and 13,209 in the plant sheet. Find these with `sql` before
  mapping (`GROUP BY` extract, `count(DISTINCT age)`), and ask which is right. It matters for the
  epoch, since the two ages fall on either side of the boundary.
- **Totals from a cut table:** `processedTotalReadCount` is the replicate's total over all OTUs, not
  over the ones kept.
- **Lake coordinates for the core:** say so in `georeferenceRemarks`. Don't add an uncertainty
  that isn't stated.
- **"BP" without "cal":** an uncalibrated radiocarbon age goes in `uncalibratedChronometricAge`,
  not in the earliest and latest fields.

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
