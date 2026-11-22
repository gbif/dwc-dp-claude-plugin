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
  - `id`, `title` and `version`, when given with `--id`, `--title` and `--version`;
  - `resources`: one per table, with `profile` `tabular-data-resource`, `mediatype` `text/csv`,
    and the table schema written out in full.
- **The table schemas inside it:**
  - field descriptors copied unchanged from the vendored DwC-DP schemas (the guide requires
    this);
  - the `primaryKey`, and every `foreignKeys` entry whose field the table has.
- **`eml.xml`:** copied in when given with `--eml`.

`package` checks first, and refuses while anything must be fixed. It never writes into a folder
that has files in it, unless `--overwrite` is given.

## What the guide requires that the data holder decides

- **Dataset identifier** (`id`): SHOULD be there, preferably a DOI. Use one they have; don't make
  one up.
- **Version** (`version`): SHOULD be there. Ask them.
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
