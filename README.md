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

You need Python 3.8 or later and DuckDB's Python package: `python3 -m pip install duckdb`.

## What it contains

- `skills/dwc-dp/SKILL.md`: the workflow Claude follows, in seven stages, and its rules: never
  invent a value, the data holder decides the model, their files are never changed, and nothing
  leaves their machine.
- `skills/dwc-dp/references/`: DwC-DP in plain words, choosing tables, the package rules, and
  recipes per kind of dataset.
- `skills/dwc-dp/schemas/1.0/`: the DwC-DP 1.0 table schemas and profile, copied from
  [tdwg/dwc](https://github.com/tdwg/dwc) at a pinned commit (see `PINNED_VERSION.md`).
- `skills/dwc-dp/scripts/dwcdp.py`: a command-line tool on DuckDB. `python3 dwcdp.py --help`
  lists its commands; it works on its own too, for example `dwcdp.py check <folder>` on any DwC-DP
  package.

## Development

```text
python3 -m unittest discover tests
python3 tools/pin_schemas.py <tdwg/dwc commit>   # move to a new DwC-DP pin
```

`CLAUDE.md` holds the rules for anyone, human or agent, working on the repository, and
`BACKLOG.md` the planned work.

## License

Apache 2.0, see [LICENSE](LICENSE). The DwC-DP schemas in `skills/dwc-dp/schemas/` are from the
Darwin Core standard by TDWG, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
