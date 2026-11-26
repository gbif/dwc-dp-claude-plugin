# dwc-dp-claude-plugin

A [Claude Code](https://claude.com/claude-code) plugin that helps a data holder turn their own
spreadsheets and database exports into a [Darwin Core Data Package](https://dwc.tdwg.org/dp/)
(DwC-DP) 1.0: specimens and collections, surveys, eDNA, observations, organism interactions or
camera traps. Claude explains the relational model with the data holder's own records, asks them
for every modelling decision, writes the mapping as a SQL file they can rerun, checks the result,
and writes the package.

Status: in development, not released.

## Try it locally

```text
claude --plugin-dir /path/to/dwc-dp-claude-plugin
```

Then ask Claude something like "Help me turn the data in this folder into a Darwin Core Data
Package".

You need Python 3.9 or later and DuckDB's Python package, version 1.4 or later:
`python3 -m pip install duckdb`. It is tested with Python 3.9 and 3.12 and DuckDB 1.4.4.

## What it contains

- `skills/dwc-dp/SKILL.md`: the workflow Claude follows, in eight stages (inspect, model, identify,
  map, validate, describe, occurrences for GBIF, package), and its rules: never invent a value, the
  data holder decides the model, their files are never changed, and nothing leaves their machine
  without their word. The only network call the tool makes is a GRSciColl lookup of institution
  and collection codes, after they agree. Installing DuckDB's excel extension, for `.xlsx` files,
  also waits for their agreement.
- `skills/dwc-dp/references/`: DwC-DP in plain words, choosing tables, interactions, assertions,
  side tables, georeferencing, the package rules, and recipes with worked examples: surveys, eDNA,
  specimens, observations and camera traps, Darwin Core Archives, dated material, and tracking.
- `skills/dwc-dp/schemas/1.0/`: the DwC-DP 1.0 table schemas and profile, copied from
  [tdwg/dwc](https://github.com/tdwg/dwc) at a pinned commit (see `PINNED_VERSION.md`).
- `skills/dwc-dp/vocabularies/`: the GBIF vocabularies GBIF reads some fields with (for example
  `occurrenceStatus`, `lifeStage`, `typeStatus`), copied from the GBIF API.
- `skills/dwc-dp/crosswalks/`: Movebank's attributes and a Movebank-to-DwC-DP crosswalk.
- `skills/dwc-dp/eml/`: GBIF's EML agent roles, for the people in the metadata.
- `skills/dwc-dp/scripts/dwcdp.py`: a command-line tool on DuckDB. `python3 dwcdp.py --help`
  lists its commands; it works on its own too, for example `dwcdp.py check <folder>` on any DwC-DP
  package.

## Development

```text
python3 -m unittest discover tests
python3 tools/pin_schemas.py <tdwg/dwc commit>   # move to a new DwC-DP pin
python3 tools/pin_vocabularies.py                # copy the GBIF vocabularies again
python3 tools/pin_movebank.py                    # copy the Movebank attributes again
python3 tools/pin_agent_roles.py                 # copy GBIF's EML agent roles again
```

The agent workflows in `.github/workflows/` (`claude*.yml`) have their schedules off; they run by
hand until the agent setup is done.

`CLAUDE.md` holds the rules for anyone, human or agent, working on the repository, and
`BACKLOG.md` the planned work.

## License

Apache 2.0, see [LICENSE](LICENSE). The DwC-DP schemas in `skills/dwc-dp/schemas/` are from the
Darwin Core standard by TDWG, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The
vocabularies in `skills/dwc-dp/vocabularies/` are from the GBIF vocabulary server. Two sources
state no licence, so only identifiers and names are copied from them, without their definitions:
Movebank's attributes in `skills/dwc-dp/crosswalks/movebank-attributes.json` (NERC Vocabulary
Server, collection MVB), and GBIF's EML agent roles in `skills/dwc-dp/eml/agent-roles.json`
(rs.gbif.org). Three test fixtures are real, published data under CC0 (camera traps, tracking and sediment eDNA), with their sources in their READMEs; the others are made up.
