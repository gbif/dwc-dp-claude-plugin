# Assertions: measurements and facts without a field

Each assertion table holds "A dwc:Assertion made by a dcterms:Agent about" its subject: a
`dwc:Event` for `event-assertion`, a `dwc:MaterialEntity` for `material-assertion`, and so on. All
of them are versions of `dwc:MeasurementOrFact` (their `dcterms:isVersionOf`), the Darwin Core term
behind the MeasurementOrFact extension of Darwin Core Archives.

In practice they hold measurements and facts without a field of their own, one row per value. For
example: water temperature and pH at a sampling site, the length and weight of a specimen, the
volume of a sample, or how a camera was set up.

## First: is there a dedicated field?

Use an assertion only for what has no field. Many measurements do have one, for example:

- **`event`:** `minimumDepthInMeters`/`maximumDepthInMeters`, `minimumElevationInMeters`,
  `minimumDistanceAboveSurfaceInMeters` and `coordinateUncertaintyInMeters`; `habitat`,
  `eventDate` and `eventTime`;
- **`material`:** `measuredMassInGrams` and `objectQuantity`;
- **`survey`:** `samplingEffortValue`/`Unit`, `sampleSizeValue`/`Unit` and
  `totalAreaSampledValue`;
- **`occurrence`:** `organismQuantity`, `sex`, `lifeStage`, `behavior` and
  `reproductiveCondition`.

`dwcdp.py suggest <source table> --table <table>` lists each column with the fields it could be,
"maybe" fields whose names contain the column's words, or a note that nothing matches.
`dwcdp.py find-term <word> --notes` searches further. A column that matches nothing after both is
an assertion candidate. Whether it is published at all is still the data holder's choice.

## Which table: what is it about?

There is an assertion table for these:

- `event-assertion`
- `occurrence-assertion`
- `material-assertion`
- `organism-assertion`
- `organism-interaction-assertion`
- `survey-assertion`
- `media-assertion`
- `molecular-protocol-assertion`
- `nucleotide-analysis-assertion`
- `chronometric-age-assertion`

The question is what the value describes, and only the data holder knows:

| Value | About the… | Table |
|---|---|---|
| water temperature, pH or salinity measured on site when sampling | sampling event | `event-assertion` |
| pH or nitrogen measured later in the lab on the soil core | material | `material-assertion` |
| volume of a water sample, weight of a bulk sample | material | `material-assertion` (mass has `measuredMassInGrams`) |
| wing length or body mass of a pinned specimen | material | `material-assertion` |
| body length of a live animal measured and released | occurrence | `occurrence-assertion` |
| a trait of a tagged individual that doesn't change between sightings | organism | `organism-assertion` |
| camera height, bait used | deployment event | `event-assertion` |
| DNA concentration of an extract | material (the extract) | `material-assertion` |
| a quality score of one analysis | nucleotide analysis | `nucleotide-analysis-assertion` |

There is no assertion table for agents, protocols, geological contexts, identifications or
sequences. A measurement about one of these needs another home. Tell the data holder and ask; don't
attach it to something else silently.

## How to write one

One row per value: a sample with temperature and pH has two rows.

| Field | What goes in it |
|---|---|
| `assertionID` | an identifier for the assertion; the thing's key and the type (`S1:waterTemperature`) are enough |
| `*_fk` | the thing it is about, such as `event_fk` or `materialEntity_fk` (required) |
| `verbatimAssertionType` | the column name as they wrote it (`water_temp_C`) |
| `assertionType` | the type in words, agreed with them (`water temperature`) |
| `assertionTypeIRI`, `assertionTypeSource` | an IRI and vocabulary for the type, only when they use one or agree to one |
| `assertionValue` | the value as written. It is text in DwC-DP 1.0, so a number keeps its form; only a decimal comma becomes a point, with their agreement |
| `assertionValueIRI`, `assertionValueSource` | for a value from a vocabulary |
| `assertionUnit` | the unit, from the column name, their documents or their answer. Never guessed |
| `assertionUnitIRI`, `assertionUnitSource` | an IRI and vocabulary for the unit, when they have one |
| `assertionEffectiveDate` | when the value held, if not the event's date (a lab value of a sample taken earlier) |
| `assertionMadeDate` | when the measurement or statement was made |
| `assertionBy`, `assertionBy_fk`, `assertionByID` | who measured |
| `assertionProtocols`, `assertionProtocol_fk` | how it was measured: a probe or a lab method |
| `assertionError` | the uncertainty, as they state it |
| `assertionRemarks` | anything else |

Several measurement columns in one sheet become assertions with one `INSERT ... SELECT`. Turn the
columns into rows with `UNPIVOT`, or with a `VALUES` list when the types and units differ per
column:

```sql
INSERT INTO event_assertion (assertionID, event_fk, verbatimAssertionType, assertionType,
                             assertionValue, assertionUnit)
SELECT s.sample || ':' || a.type, s.event, a.verbatim, a.type, a.value, a.unit
FROM src_samples s,
     LATERAL (VALUES ('water_temp_C', 'water temperature', replace(s.water_temp_C, ',', '.'), '°C'),
                     ('salinity',     'salinity',          s.salinity,                     'PSU'))
       AS a(verbatim, type, value, unit)
WHERE a.value IS NOT NULL;
```

Here the units come from the column name (`_C`) and the data holder's methods (salinity in PSU).

## Don't

- Don't invent a unit, method, vocabulary or IRI that their data or documents don't state.
- Don't put a value that has a dedicated field in an assertion as well.
- Don't add the measurement as a custom column on the table: the guide says custom fields SHOULD
  NOT be added.
- Don't merge two columns into one assertion, such as a value and its unit kept in separate columns
  of their sheet; map them to `assertionValue` and `assertionUnit`.

## Sources

- DwC-DP 1.0 table schemas `*-assertion` (the vendored copies): fields and descriptions. In 1.0,
  `assertionValue` is a string and there is no separate numeric value field.
- The DwC-DP guide, section 3.3, on custom fields.
- Darwin Core conceptual model, https://dwc.tdwg.org/cm/.
