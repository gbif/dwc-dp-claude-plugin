# Choosing tables

Ask these questions about the data holder's records, in this order. Each "yes" adds the tables in
its row. Before proposing a table, run `dwcdp.py describe <table>` and use its own definition. This
list is a starting point, not the definition. A dataset that fits none of it is a question for the
data holder (and, if it stays open, for the maintainers).

| Question | If yes |
|---|---|
| Were organisms seen, caught, heard, photographed or detected somewhere at some time? | `event` for each visit or sampling, `occurrence` for each organism (or group) recorded there |
| Did the visits sit inside something larger: a project, an expedition, a transect, a trap deployment? | more `event` rows, linked by `parentEvent_fk` |
| Was it a planned survey, with a method and a list of what was looked for, so that "not found" means something? | `survey` (with `event_fk`), `survey-target` and `survey-target-descriptor`, `survey-survey-target` |
| Do they record absences, or counts of zero? | `occurrence` rows with `occurrenceStatus`. A survey makes them interpretable |
| Was physical material kept: specimens, tissue, soil or water samples, extracts? | `material` (with `collectionEvent_fk`). For subsamples, `derivedFromMaterialEntity_fk` |
| Are names given to organisms or specimens, perhaps more than once, by named people? | `identification` and `identification-taxon`. For several people or roles, `identification-agent-role` |
| Was DNA sequenced (eDNA, metabarcoding, barcoding)? | `nucleotide-analysis`, `nucleotide-sequence`, `molecular-protocol`; usually `material` for the sample |
| Do they record interactions between organisms: visits, predation, parasitism? | `organism-interaction`, linking two `occurrence` rows |
| Is the same individual recorded several times (tags, rings, named animals)? | `organism`, with `occurrence.organism_fk` |
| Are there images, sound or video? | `media`, and `occurrence-media`, `material-media`, `event-media` and so on for what they show |
| Are there measurements or facts with no DwC-DP field, such as water temperature, pH, body length, sample volume or trap height? | the `*-assertion` table of the thing they describe (`event-assertion`, `material-assertion`, `occurrence-assertion`, ...); see `assertions.md` |
| Are people or organisations named, and do they want them identified (ORCID, ROR) or credited by role? | `agent`, `agent-identifier`, and the `*-agent-role` tables |
| Do they describe methods, cite literature, or state rights per record? | `protocol` and `*-protocol`, `bibliographic-resource` and `*-reference`, `usage-policy` and `*-usage-policy`, `provenance` |
| Rocks, fossils, dating? | `geological-context`, `chronometric-age`, `geological-material` |

Then:

- `dwcdp.py order <tables>` gives the order to fill them in;
- `dwcdp.py init <tables>` lists the tables the chosen ones can point to that aren't chosen yet.
  Add them only when the data have something for them.

## Where does this column go?

`dwcdp.py find-term <word>` searches field names and descriptions across all tables, with
`--notes` to search the usage notes too. Some terms exist in several tables
(`informationWithheld` in `event`, `occurrence`, `material` and `survey`, for example). Put a value
on the thing it describes: a visit's observer on the event (`recordedBy`), a specimen's
preparation on the material.

## Notes

- **Phylogenetic trees:** these tables are marked `defer` in DwC-DP 1.0 and are not part of the
  vendored schemas.
