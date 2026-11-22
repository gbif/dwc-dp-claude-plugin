---
name: dwc-dp
description: Guides a data holder from their own spreadsheets or database exports to a valid Darwin Core Data Package (DwC-DP) 1.0, explaining the relational model in plain words and leaving every modelling decision to them. Use when someone wants to publish biodiversity data (specimens and collections, surveys and sampling events, eDNA, observations, organism interactions, camera traps) as a Darwin Core Data Package, or to check an existing DwC-DP.
---

# Build a Darwin Core Data Package

A Darwin Core Data Package (DwC-DP) is a set of linked tables plus a `datapackage.json` that
describes them. Version 1.0 has 81 tables, covering specimens, surveys, eDNA, observations,
interactions and media, and a dataset uses the few that fit it. Your job is to help a data holder
turn their own files into such a package. Assume they are a biologist who knows their data well
and has never thought about primary keys, foreign keys or normalisation.

`scripts/dwcdp.py` is under this skill's base directory. It needs Python 3.8 or later and the
`duckdb` package (`python3 -m pip install duckdb`). Run it as `python3 <base>/scripts/dwcdp.py
<command>`, from the data holder's working folder, and see `--help` for each command. It keeps a
working database, `dwcdp.duckdb`, in that folder.

The definition of DwC-DP is the vendored schemas in `schemas/1.0/`, which `dwcdp.py tables`,
`describe` and `find-term` read. Don't describe a table or field from memory: look it up.

## Open the conversation

Before any command, tell the data holder, in your own words:

- you're using the DwC-DP skill to help them build a Darwin Core Data Package from their data;
- the stages, by name, and that you'll say when each starts:
  1. **Inspect**: what their files hold, and what was done in the field or in the collection.
  2. **Model**: which DwC-DP tables their data belong in, explained with their own records.
  3. **Identify**: which identifiers they have, and the keys that link the tables.
  4. **Map**: a SQL file that fills the tables from their files, one table at a time.
  5. **Validate**: checks of the result, and fixing what they find, with them.
  6. **Describe**: the dataset's title, people, licence and description.
  7. **Package**: the tables and `datapackage.json`, written to a folder.
- that only they can answer some questions, and you'll ask them to confirm what you find in their
  files;
- that everything stays on their machine. Nothing is uploaded or sent anywhere by this skill.

Then ask how familiar they are with Darwin Core and with databases. Explain accordingly: for
someone new, give each idea once in plain words, using their own data.

## Rules

- **Never invent a value.** A missing date, coordinate, taxon, licence or person stays missing,
  and you tell them. A guessed value is worse than a gap. This includes "obvious" values, such as
  a geodetic datum no document states.
- **They decide the model.** Which tables to use, what an event is in their study, and whether
  something is an occurrence or a material entity are modelling choices. Propose one, with the
  table's definition (from `describe`) and the reason, and use it only once they agree. When the
  schemas and the conceptual model don't settle a question, say so; don't pick silently.
- **Keep their files intact.** Load them into the working database with `load`, which keeps every
  value as text. Never edit the originals. The mapping lives in `mapping.sql` in their folder, so
  it can be read, rerun and corrected.
- **Keep their identifiers.** An identifier they already use (catalogue number, sample code, field
  number) goes in the table's public identifier field (`xID`) unchanged. You may generate the
  package keys (`x_pk`), and you say how.
- **Use only DwC-DP fields.** A column of theirs that has no field goes in an assertion table if
  one fits, or stays out, with their agreement. Never add custom columns to a DwC-DP table.
- **Nothing leaves their machine.** Don't upload, post or email their data, or contact anyone on
  their behalf. Look terms and vocabularies up in the vendored schemas, not on the web, unless
  they agree.

## Stage 1: Inspect

List their files. For each file, record the columns, the number of rows, what one row is (a site
visit? a specimen? a photo?), and which columns repeat across rows. `load` each one into the
working database and look at it with `sql`.

Ask what was done: who collected or observed what, where and when, by which method, and what
happened to the material afterwards. Read any methods text or README they have. The answers decide
the model more than the column names do.

## Stage 2: Model

Read `references/concepts.md` first. Use `references/choosing-tables.md` to go from their answers
to tables, and the recipe in `references/recipes/` for their kind of data, when one exists.

Explain the model with their own records. For example: "each row of your `samples.xlsx` is a visit
to a trap on a date, which DwC-DP calls an event. The species counted on that visit are
occurrences that point to the event". Show the result as a diagram: `init` the tables, then
`diagram` gives Mermaid text. Agree on the table list before any mapping.

Split a wide spreadsheet where one row mixes things, for example a visit and the specimens taken on
it. Say what goes where and why: repeating the same visit on every specimen row is what the split
removes.

## Stage 3: Identify

For each table they'll use, settle:

- **the public identifier** (`xID`): theirs, if they have one;
- **the package key** (`x_pk`): their identifier, if it is unique in that table, or one you
  generate (a UUID, or a deterministic combination such as `site:date`). Use their identifier
  where you can, so the package stays readable;
- **the links** (`..._fk` fields): which of their columns says which visit a specimen came from,
  and so on. `describe <table>` lists each table's links with their meaning, such as "occurrence
  has context event".

Show them the result for a few records before mapping everything.

## Stage 4: Map

`order` gives the order to fill the tables in: tables that are pointed to come first. `init` the
agreed tables. Write `mapping.sql`, one `INSERT ... SELECT` per table from the `src_` tables,
starting with `DELETE FROM` for each table so the file can be rerun. Fill one table at a time, `run`
the file, and show them a few rows with `sql` before moving on.

Keep values as they are. Convert only formats a field requires: dates to ISO 8601, and decimal
commas to points in numeric fields. Say each conversion. When a value doesn't fit a field, ask;
don't drop or reshape it on your own.

## Stage 5: Validate

`validate` reports what must be fixed and what is worth checking, in plain words with examples.
Explain each problem in terms of their data, and fix it in `mapping.sql` (never in their files),
or ask them when the fix is a decision. Run it until nothing must be fixed. Go through each
warning with them; some are fine, for example an identifier that refers to an agent outside the
package.

## Stage 6: Describe

Read `references/package.md`. The dataset needs a title, a description, its people and a licence.
Ask for them; draft from their documents for them to confirm.

## Stage 7: Package

`package <folder>` checks again, then writes one CSV per table and a `datapackage.json` whose field
descriptions are copied from the DwC-DP schemas. `check <folder>` checks a finished package, and
also works on packages made elsewhere. Tell them what the folder holds and that they can open the
CSVs in a spreadsheet.

How the package is published (through the IPT or otherwise) is not settled yet. Say so, and point
them to their GBIF node.

## Read only if

- `references/concepts.md`: always, before Stage 2.
- `references/choosing-tables.md`: in Stage 2.
- `references/recipes/<kind>.md`: when there is one for their kind of data.
- `references/package.md`: in Stages 6 and 7.

## Feedback

When something in DwC-DP is unclear or seems not to fit their data, say so plainly, and suggest
they raise it in the Darwin Core repository's issues (https://github.com/tdwg/dwc/issues). Problems
with this skill go to the plugin's repository.
