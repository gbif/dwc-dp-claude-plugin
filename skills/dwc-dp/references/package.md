# The package

The rules are from section 3 of the DwC-DP guide (https://dwc.tdwg.org/dp/), which is normative.
`dwcdp.py package` follows them, and `dwcdp.py check` tests them.

## What `package` writes

- **One CSV per table:**
  - comma-separated, UTF-8, with a header, named after the table (`event.csv`);
  - only the fields that hold a value somewhere, plus required ones, in the schema's order;
  - an empty cell means no value.
- **`datapackage.json`:**
  - `profile`: `https://rs.tdwg.org/dwc-dp/1.0/dwc-dp-profile.json`, which is required;
  - `created`: when the package was written;
  - `name`, `id`, `title` and `version`, when given with `--name`, `--id`, `--title` and
    `--version`. `name` is a short identifier in lower-case letters, digits and `-._/`;
  - `resources`: one per table, with `profile` `tabular-data-resource`, `mediatype` `text/csv`,
    and the table schema written out in full.
- **The table schemas inside it:**
  - field descriptors copied unchanged from the vendored DwC-DP schemas (the guide requires
    this);
  - the `primaryKey`, and every `foreignKeys` entry whose field the table has.
- **`eml.xml`:** copied in when given with `--eml`.

`package` checks first, and refuses while anything must be fixed. It never writes into a folder
that has files in it, unless `--overwrite` is given.

## `check` and GBIF's DwC-DP analyser

GBIF checks every DwC-DP it crawls with its DwC-DP analyser (https://github.com/gbif/dwc-dp-analyser).
`check` makes the same checks, at the same levels, so data holders don't need to install it. The
`--json` report names the analyser's violation type for each finding (`analyser`), and the text
report ends with how many of the errors the analyser would report. The alignment is with release
0.0.16, read from its source. It has not yet been confirmed by running the analyser on the
fixtures.

`check` has more errors than the analyser, all from rules of the DwC-DP guide or the schemas:

- `primaryKey` other than the schema's (guide 3.3);
- `mediatype` other than `text/csv` (3.2.2);
- a schema given as a reference instead of an object (3.2.2);
- file columns that don't match the declared fields in order and number (3.3);
- required fields with empty values, values outside `minimum`/`maximum`, and duplicates in
  unique fields;
- a link that has a value but no table to point to, and rows that point to themselves.

It also warns about references by identifier that match nothing in the package, identifications
based on more than one kind of evidence, and values outside GBIF's vocabularies.

It follows the analyser where the analyser is more lenient than the guide's wording. Tell the data
holder about these, even when `check` passes:

- a field `type` other than the schema's is a warning, though the guide says descriptors MUST be
  copied;
- the same goes for a resource `profile` other than `tabular-data-resource`, and for a declared
  relationship the schema doesn't define;
- a custom field is information only (the guide: SHOULD NOT).

Two of the analyser's warnings need explaining:

- **A changed `description` is a warning,** though the guide says a definition MAY differ in
  context (3.4).
- **An identifier that refers to a table not in the package** (for example `recordedByID` with no
  `agent` table) is a warning (`FK_UNKNOWN_REFERENCE_RESOURCE`), though the schema says such
  identifiers MAY point outside the package. Packages from `package` have it whenever they use such
  identifiers. It is expected, and doesn't make the package invalid.

Not checked by `check`: EML against the EML 2.2.0 schema.

## What the guide requires that the data holder decides

- **Dataset identifier** (`id`): SHOULD be there, preferably a DOI. Use one they have; don't make
  one up.
- **Version** (`version`): SHOULD be there. Ask them.
- **Name** (`name`): RECOMMENDED by the Data Package specification. GBIF's analyser warns
  without it. Propose one from the title, such as `beetles-mols-2024`, and use it once they
  agree.
- **Metadata:** title, description, people, licence.
  - **What the guide says:** `eml.xml` is optional (section 3, "MAY have an EML metadata file"),
    and when present it "MUST follow the Ecological Metadata Language specification". The
    descriptor MAY also carry dataset metadata (section 3.1.6).
  - **What GBIF does,** as of 2026-11-22:
    - its crawler forwards `eml.xml` to the registry when the package has one, and the
      `datapackage.json` metadata otherwise (`DwcDpMetasyncCallback` in gbif/crawler);
    - GBIF's DwC-DP validator (gbif/dwc-dp-analyser) checks an `eml.xml` when present: well-formed,
      with `<title>` and `<creator>`, and valid against EML 2.2.0.
  - **Not settled yet:** which of the two this skill writes. Until then, collect the metadata with
    the data holder, use `--title`, and pass an `eml.xml` they already have (for example the one
    in their Darwin Core Archive) with `--eml`.

## Not covered yet

- Compressed packages (`.gz`).
- Tables in other dialects (TSV and so on). `check` reads them when the `dialect` says so;
  `package` always writes standard CSV.
- Writing `eml.xml` from the data holder's answers.
