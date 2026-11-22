# Recipes

One file per kind of dataset: `survey.md`, `edna.md`, `specimens.md`, `observations.md` (which
covers observations, interactions and camera traps). There are none yet. Each is written from an
issue, with a fixture under `tests/fixtures/` that validates.

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
