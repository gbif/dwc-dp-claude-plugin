# Recipes

One file per kind of dataset. Each is written from an issue, with a worked example under
`tests/fixtures/` that a test validates, packages and checks.

| Recipe | For | Worked example |
|---|---|---|
| `survey.md` | surveys and sampling events: visits, counts, targets, absences, material kept | `survey-point-counts/`, `survey-malaise-bulk/` |
| `specimens.md` | specimens and collections: material, parts and derived material, determinations | `specimens-beetles/`, `specimens-mammal-parts/` |
| `observations.md` | observations, interactions and camera traps (Camtrap DP) | `observations-pollinators/`, `observations-camtrap/` |
| `edna.md` | eDNA and metabarcoding: several markers, kept samples, filters and extracts | `edna-two-markers/` |
| `paleo.md` | cores, dated material and geological time: ages, age-depth models, epochs, depth in core, sedaDNA | `edna-sediment-core/` |
| `dwca.md` | Darwin Core Archives: Occurrence and Event cores, MeasurementOrFact, Multimedia, DNA derived data, `associatedTaxa` | `dwca-occurrence-core/`, `dwca-associated-taxa/`, `dwca-event-core/`, `dwca-dna-derived/` |

Interactions between organisms turn up in every kind of dataset, often unnamed: a host, a prey, the
tree a fungus grew on. `../interactions.md` covers them for all recipes.

A recipe holds:

- **When it applies:** what the data holder's files usually look like.
- **Tables:** which tables, and why. Cite each table's description from the schema.
- **Keys:** where the public identifiers usually come from, and how the package keys are made.
- **Mapping:** a worked `mapping.sql` for the fixture, explained step by step.
- **Choices:** the decisions the data holder makes, with the options and their consequences.
  Never one taken for them.
- **Pitfalls:** what goes wrong, and what `validate` says when it does.
- **Sources:** the examples it learned from (repository, path, commit) and what was different in
  1.0.

The examples in https://github.com/gbif/dwc-dp-examples were written before 1.0. Most still use
public identifiers as keys (`eventID` where 1.0 has `event_pk`), so `check` refuses them. Learn
from how they split the data, not from their field names.
