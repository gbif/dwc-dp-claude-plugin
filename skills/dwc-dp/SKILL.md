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
- **Names go in `identification`.** One identification per name, of the material or based on the
  occurrence, media or sequence it was made from. When a record has an identification, its own
  name fields (`scientificName`, `identifiedBy`, ...) stay empty.
- **Material: always ask about the collection.** Whenever their data get a `material` table, ask
  whether the material is held in a collection, and if so which institution and which collection,
  and whether another institution owns it. Ask even when their files have no such columns, as for
  eDNA samples, trap catches or cores. Ask before mapping it, and write down the answer: a "no"
  leaves those fields empty. See "Institution and collection" in Stage 3.
- **Use only DwC-DP fields.** A column of theirs that has no field names another organism (an
  interaction, see `references/interactions.md`), goes in an assertion table if one fits, or stays
  out, with their agreement. Never add custom columns to a DwC-DP table. See
  `references/assertions.md`.
- **Compare sources that say the same thing.** When two files, or a file and a label or paper,
  give the same fact for a record (where, when, whether a sample was taken, which OTUs or samples
  exist), compare them with `sql` before using either, and show them the differences. Disagreement
  usually means a wrong join, a typo or a placeholder, and only they can say which. See Stage 1 and
  Stage 4.
- **Nothing from memory goes in the package.** References, DOIs, primer names and sequences,
  protocol citations, funder identifiers, ORCIDs: take them from their documents or from them. If
  you know one from memory, say so, mark it as unchecked, and use it only once they have checked
  it.
- **Nothing leaves their machine.** Don't upload, post or email their data, or contact anyone on
  their behalf. Terms and vocabularies are in the copies bundled with this skill (`describe`,
  `find-term`, `vocab`). Anything that uses the network needs their agreement first, each kind
  once, with what it sends said plainly:

  | Lookup | What it sends | Note |
  |---|---|---|
  | `grscicoll` | institution and collection codes | the tool's only network call |
  | installing software (`pip install`, DuckDB extensions) | nothing of theirs | it changes their machine; use what is installed when you can |
  | reading documentation or vocabularies on the web | nothing of theirs | say where an answer came from |
  | place lookups (reverse geocoding, gazetteers) | their coordinates or place names | locations are their data and can be sensitive, such as nests or rare plants. Follow the service's usage policy, and keep the results in a file in their folder |
  | people lookups (ORCID, staff pages) | people's names | personal data. Better to ask them for the ORCIDs. A name can match several people: they confirm each match |

- **The goal is a valid package.** This skill ends when `check` passes on their package.
  Publishing it is a separate step outside this skill.

## Stage 1: Inspect

List their files. For each file, record the columns, the number of rows, what one row is (a site
visit? a specimen? a photo?), and which columns repeat across rows. `load` each one into the
working database and look at it with `sql`.

What `load` does and says:
- **Encoding:** a text file that isn't UTF-8 is refused. The message shows the first line it can't
  read as Latin-1 and as Windows-1252 (cp1252). Ask which their software writes, or which reading
  shows their letters right, then load it with `--encoding`. Don't pick one yourself.
- **Wide tables,** with one column per OTU, species or sample: `--unpivot <id columns>` keeps those
  columns and turns every other column into a row, named with `--into` (for example
  `--into otu,reads`). Empty cells are left out, zeros kept, and it says how many of each.
- **Empty values become NULL.** Test them with `IS NULL`; `= ''` finds nothing.
- **One column** whose values contain commas or semicolons: each line may be wrapped in quotes, or
  the separator is another one. Look at the file's first lines. Lines wrapped in quotes load with
  `--unwrap`; another separator with `--sep`.

`sql` runs one query, or a script with `--file`. Both are read-only, but `CREATE TEMP VIEW`,
`TEMP TABLE` and `TEMP MACRO` work within one call. A column or alias that is a SQL keyword
(`name`, `positional`, `numeric`) has to be in double quotes; the error says so.

A Darwin Core Archive (a `.zip` with `meta.xml`) goes in with `load-dwca`, which stages the core
and each extension as `src_dwca_<row type>` tables, with columns named after their Darwin Core
terms. Its `eml.xml` is the first source for Stage 6. The archive's columns already have Darwin
Core names, but a DwC-DP table is not one archive file: the core usually splits into several
tables (for example the event of each occurrence). `suggest` matches the archive's columns by
term, and `references/recipes/dwca.md` covers the rest.

Look at the values, not only the columns:
- **Placeholders.** For each column, ask what an empty cell means, and what a `0`, `-999`, `NA`,
  `unknown` or default date means. Lab and field templates are often prefilled: a dry mass of 0 can
  mean "not weighed", not 0 mg. Count each column's most common values with `sql`. A value repeated
  far more often than the rest is worth asking about. A placeholder stays out of the package.
- **Sets that should match.** When files list the same things, measure how far they overlap:
  samples in the field sheet and in the lab sheet, OTUs in the read table, the sequences and the
  taxonomy, records marked "not done" that have data anyway. Show the counts (in both, only in one,
  only in the other) and ask which set to publish. Totals such as `processedTotalReadCount` depend
  on the answer.

For each source table, `suggest <table>` lists its columns with the DwC-DP fields they could be.
Read a few values of each column with no field, and sort it:
- **Does it name another organism?** Examples: a host, a prey, a flower visited, or the tree a
  fungus grew with (`associatedTaxa`, "on *Betula*"). Then it is an interaction between two
  organisms, never an assertion. See `references/interactions.md`.
- **Otherwise,** it is a candidate for an assertion: a measurement or fact such as pH, water
  temperature, body length or sample volume.

Note them for Stage 2.

Ask what was done: who collected or observed what, where and when, by which method, and what
happened to the material afterwards. Read any methods text or README they have. The answers decide
the model more than the column names do.

## Stage 2: Model

Read `references/concepts.md` first. Use `references/choosing-tables.md` to go from their answers
to tables, and the recipe in `references/recipes/` for their kind of data, when one exists.

Explain the model with their own records. For example: "each row of your `samples.xlsx` is a visit
to a trap on a date, which DwC-DP calls an event. The species counted on that visit are
occurrences that point to the event". Show the result as a diagram: `init` the tables, then
`diagram` gives Mermaid text with each table's keys and links. Once there are rows, `summary` shows
the structure with counts, in plain text. Agree on the table list before any mapping. A table that
turns out to have nothing in it is left out of the package; `drop` removes it from the database.

For every column without a field, settle with them:
- whether it is a dedicated field after all (`find-term`);
- whether it names a second organism, which makes it an `organism-interaction` with an occurrence
  of that organism. `references/interactions.md` has the questions, and the type of interaction is
  theirs to give;
- whether it is a measurement or fact to keep as an assertion, and about which thing (the event,
  the material, the occurrence…). `references/assertions.md` has the question and the tables;
- or whether it stays out.

Ask for units and methods; never guess them.

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

### Institution and collection

When `material` is among their tables, ask, every time and before mapping it:

1. Is the material, or any of it, held in a collection now? For example specimens in a museum,
   samples in a biobank, extracts in a lab's freezer collection, cores in a core repository.
2. If so, which institution has it in its care, and which collection? The codes they publish under
   go in `institutionCode` and `collectionCode`, as they give them; never fill them in from memory.
3. Does another institution own it? That goes in `ownerInstitutionCode` and `ownerInstitutionID`.
4. Does it differ between their records, for example specimens in a museum and extracts in a lab?
   Then the fields differ by row.

For the identifiers, `institutionID` and `collectionID` should come from a registry. With their
agreement, `grscicoll` looks their codes up in GRSciColl and shows every identifier it holds; they
choose. See `references/recipes/specimens.md`.

If none of it is in a collection, the fields stay empty. Say so in `mapping.sql`, so the answer
isn't asked again. `init` reminds you of this question when it creates `material`.

## Stage 4: Map

`order` gives the order to fill the tables in: tables that are pointed to come first. `init` the
agreed tables. Write `mapping.sql`, one `INSERT ... SELECT` per table from the `src_` tables,
starting with `DELETE FROM` for each table so the file can be rerun. Fill one table at a time, `run`
the file, and show them a few rows with `sql` before moving on.

Places given as routes or polygons, or in UTM: `run` and `sql` have functions for a shape's center
and radius and for UTM to latitude and longitude. See `references/georeferencing.md`; how a point
and its uncertainty are made is theirs to agree.

Check every join between their files:
- **Count the rows** before and after. A join that adds rows (a key that isn't unique on one side)
  or loses them (keys that don't match) is reported to them, with examples, before it goes in.
- **A key that looks obvious can be wrong.** A route number that is 1 or 2 per volunteer, or a
  sample code reused in another year, joins without an error and gives wrong places.
- **When another source gives the same fact,** such as coordinates on a label, compare the result
  with it. Show them the records that differ by more than they would expect.

Keep values as they are. Convert only formats a field requires: dates to ISO 8601, and decimal
commas to points in numeric fields. Say each conversion. In ISO 8601 a date and a time are joined
by `T`, not a space, and both go in `eventDate`, as in the schema's examples (`2009-02-20T08:40Z`,
`2018-06-02T12:40/13:05` for an interval within a day). When a value doesn't fit a field, ask;
don't drop or reshape it on your own.

GBIF reads some fields with its vocabularies, for example `occurrenceStatus`, `lifeStage`, `sex`
and `typeStatus`. `vocab` lists these fields, and `vocab <table.field>` lists a field's concepts
and labels. Where their value is a label of a concept, writing the concept name is clearer: show
them the pairs and convert only the ones they agree to. A value that fits no concept stays as it
is; `validate` warns about it.

## Stage 5: Validate

`validate` reports what must be fixed and what is worth checking, in plain words with examples.
It checks the schemas' rules (required fields, unique keys, links that resolve, value ranges) as
errors, and GBIF's vocabularies as warnings, since DwC-DP itself requires none.
Explain each problem in terms of their data, and fix it in `mapping.sql` (never in their files),
or ask them when the fix is a decision. Run it until nothing must be fixed. Go through each
warning with them; some are fine, for example an identifier that refers to an agent outside the
package.

## Stage 6: Describe

Read `references/package.md`. `metadata-template` writes an empty `metadata.json`. Fill it in with
them:
- **The essentials:** title, description, creators, contacts and licence.
- **People with other roles:** `associatedParties`, each with a role from GBIF's agent role
  vocabulary, such as `principalInvestigator`, `originator`, `processor` or `distributor`.
  `references/package.md` lists them all, and `package` refuses any other role.
- **Optional:**
  - keywords, methods, language, and a description of where;
  - the taxa covered;
  - the project, with its personnel, funding and awards;
  - other identifiers of the dataset.

Draft from their documents and confirm each value; never choose a licence for them, and never
give a person a role they didn't give. `package` writes
it both as `eml.xml` and in `datapackage.json`, and computes the coverage from the events.

## Stage 7: Package

`package <folder> --name <name> --metadata metadata.json` checks again, then writes one CSV per table and a `datapackage.json`
whose field descriptions are copied from the DwC-DP schemas. Agree on the name with them first
(`references/package.md`). `check <folder>` checks a finished package, including the checks GBIF's
own DwC-DP analyser makes, and also works on packages made elsewhere. The package is done when
`check` reports nothing that must be fixed. Explain each warning that remains, including the
expected one for identifiers that point outside the package. Tell them what the folder holds and that they can open the
CSVs in a spreadsheet.

Then show them what was made. Run `summary` and put its output in your reply as it is, in a code
block: the command's own output may be folded away in their terminal. It holds:
- the tables and the number of rows in each;
- how the tables link, as a tree that reads as an entity-relationship diagram;
- a few example rows of each table, with only the columns that have values.

Walk them through it with their own records: "each of your 1.3 million finds is an occurrence, under
the event of its date and place". Then tell them they can ask questions about the result in their
own words, such as how many records per year or which names are most common. Answer those with
`sql` against the working database. It is read-only, so nothing in the package changes. For a
question that needs several steps, write a script with temporary views and run it with
`sql --file`.

This is where the skill ends. Publishing the package is not part of it.

## Read only if

- `references/concepts.md`: always, before Stage 2.
- `references/choosing-tables.md`: in Stage 2.
- `references/recipes/<kind>.md`: when there is one for their kind of data.
- `references/interactions.md`: when a record names another organism (host, prey, plant,
  `associatedTaxa`).
- `references/assertions.md`: when a column has no DwC-DP field and names no organism.
- `references/side-tables.md`: when a record has roles, extra identifiers, references, protocols,
  sources, rights or media beyond what the recipe uses.
- `references/georeferencing.md`: when places are shapes (routes, transects, polygons), UTM or
  other projected coordinates, or have no coordinates.
- `references/package.md`: in Stages 6 and 7.

## Feedback

When something in DwC-DP is unclear or seems not to fit their data, say so plainly, and suggest
they raise it in the Darwin Core repository's issues (https://github.com/tdwg/dwc/issues). Problems
with this skill go to the plugin's repository.
