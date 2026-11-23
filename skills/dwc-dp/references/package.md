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
0.0.16. It was read from its source, and confirmed by running that release on 18 test packages
(a good one and 17 broken in different ways): the verdicts, findings and levels matched, except
for the two differences below. The
reports are kept in `tests/fixtures/analyser-0.0.16/`.

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

Differences from the analyser on purpose:

- **EML schema:** `check` doesn't check EML against the EML 2.2.0 schema
  (`EML_XSD_VIOLATION`).
- **Malformed `eml.xml`:** `check` reports it as a warning. The analyser reports it as an error,
  but its verdict ignores it.

## What the guide requires that the data holder decides

- **Dataset identifier** (`id`): SHOULD be there, preferably a DOI. Use one they have; don't make
  one up.
- **Version** (`version`): SHOULD be there. Ask them.
- **Name** (`name`): RECOMMENDED by the Data Package specification. GBIF's analyser warns
  without it. Propose one from the title, such as `beetles-mols-2024`, and use it once they
  agree.
## Metadata: `metadata.json`, written as `eml.xml` and in `datapackage.json`

The dataset's metadata is written twice, from one file the data holder confirms:

- **`eml.xml`:** EML 2.2.0, which the guide allows (section 3, "MUST follow the Ecological Metadata
  Language specification"). GBIF's crawler forwards `eml.xml` to the registry when a package has
  one (gbif/crawler `DwcDpMetasyncCallback`).
- **`datapackage.json`:** the Data Package specification's own properties (section 3.1.6):
  `title`, `description`, `licenses`, `contributors`, `keywords` and `homepage`. A reader of the
  descriptor alone has them too.

`dwcdp.py metadata-template` writes an empty `metadata.json`. Fill it in with the data holder:
draft from their documents (a paper, a methods text, an archive's `eml.xml`), and show them each
value. `package --metadata metadata.json` refuses a file without a title, a creator and a contact.
Those are what an EML dataset requires.

| Key | What | Written to |
|---|---|---|
| `title` | the dataset's title | EML `title`; descriptor `title` |
| `description` | what the dataset is; paragraphs separated by a blank line | EML `abstract`; descriptor `description` |
| `license` | `CC0-1.0`, `CC-BY-4.0` or `CC-BY-NC-4.0`, or `{"name", "path", "title"}` for another | EML `intellectualRights` and `licensed`; descriptor `licenses` |
| `creators` | the people or organisations who made the dataset: `givenName`, `surName`, `organization`, `email`, `orcid` | EML `creator`; descriptor `contributors` with role `author` |
| `contacts` | whom to ask about it, the same keys | EML `contact`; descriptor `contributors` with role `maintainer` |
| `metadataProviders` | who wrote the metadata, if different | EML `metadataProvider` |
| `keywords` | a list | EML `keywordSet`; descriptor `keywords` |
| `language` | the language of the data, as they state it | EML `language` |
| `homepage` | a web page about the dataset | descriptor `homepage` |
| `methods` | a list of method steps | EML `methods` |
| `coverage.geographicDescription` | where, in words | EML `geographicCoverage`, with the bounding box from the events |
| `id`, `version` | a DOI or other identifier, and the dataset's version | EML `alternateIdentifier`; descriptor `id`, `version` |

The coverage is computed from the data: the bounding box from the events' coordinates and the date
range from their `eventDate`s. `package` prints it; show it to the data holder. EML requires a
`geographicDescription` with a bounding box, so without one there is no geographic coverage, and
`package` says so.

Rules:
- **Licence:** GBIF publishes under CC0 1.0, CC BY 4.0 and CC BY-NC 4.0. Which one is the data
  holder's decision, and there is no default.
- **People:** only people they name, with only the email and ORCID they give.
- **An archive's `eml.xml`:** to keep it unchanged instead, use `--eml eml.xml`. `--metadata` then
  still fills the descriptor.

The generated `eml.xml` was checked against the EML 2.2.0 schema (NCEAS/eml `RELEASE_EML_2_2_0`)
when this was written. `check` itself tests only that `eml.xml` is well-formed and has a title and
a creator. GBIF's analyser validates it against the schema.

## Not covered yet

- Compressed packages (`.gz`).
- Tables in other dialects (TSV and so on). `check` reads them when the `dialect` says so;
  `package` always writes standard CSV.
