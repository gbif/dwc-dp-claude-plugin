# Side tables: roles, identifiers, references, protocols, rights and media

About half of the 81 tables link a main table to one more kind of thing. They come in families
named `<table>-<kind>`, and every member of a family has the same fields apart from the link to its
own table. So once one member is clear, the rest are too. `dwcdp.py describe <table>` shows the
exact fields of each.

Use one only when the data have something for it, and say which family it is when you propose it.
None of these tables has a key of its own (no `_pk`): a row is a link plus a few facts about it.

## The families

| Family | Members (the main table before the suffix) | One row says | Required | Worked example |
|---|---|---|---|---|
| `-agent-role` | agent, chronometric-age, event, identification, material, media, molecular-protocol, occurrence, organism-interaction, survey | this agent had this role for this record | the record, `agent_fk`, `agentRoleOrder` | `media-agent-role` (observations), `material-agent-role` (specimens, eDNA), `event-agent-role` (tracking, camera traps) |
| `-identifier` | agent, event, material, media, occurrence, organism, survey | this record also has this identifier | the record, `identifier` | none |
| `-reference` | chronometric-age, event, identification, material, molecular-protocol, occurrence, organism, organism-interaction, protocol, survey | this record is mentioned in this publication | the record | `protocol-reference`, `molecular-protocol-reference` (paleo) |
| `-protocol` | chronometric-age, event, material, occurrence, survey | this record followed this protocol | both links | none |
| `-provenance` | event, material, media | this record came from this source | both links | none |
| `-usage-policy` | event, material, media | these rights apply to this record | the record; also `usagePolicy_fk` for material and media | none |
| `-media` | agent, chronometric-age, event, geological-context, material, occurrence, organism-interaction | this media item shows this record | both links | `occurrence-media` (observations), `event-media` (camera traps) |
| `-assertion` | chronometric-age, event, material, media, molecular-protocol, nucleotide-analysis, occurrence, organism, organism-interaction, survey | a measurement or fact about this record | the record | `assertions.md` |

## How each family is filled

- **`-agent-role`:**
  - `agentRole` names the role, in the data holder's words or from a vocabulary they use
    (`agentRoleIRI`, `agentRoleSource`).
  - `agentRoleOrder` is required: 1 for a single person, or the order of authors.
  - `agentRoleDate` says when, for example when an extract was made.
  - `agent-agent-role` relates two agents, such as a person and their institution.
- **`-identifier`:** one row per extra identifier of the record (an old catalogue number, a barcode,
  a GenBank accession), with `identifierType`. The record's own public identifier stays in its
  `xID` field. A list in `otherCatalogNumbers` is the alternative for material; use one or the
  other.
- **`-reference`:** a row in `bibliographic-resource` for the publication, and a link with
  `relationshipType` (schema examples: `cited in`, `referenced`). `reference_fk` is not required,
  but a link without it says nothing; leave the row out instead.
- **`-protocol`:** a row in `protocol` (with `protocolType`, `protocolName` and
  `protocolReferences`), and a link from each record that followed it. Use this when a method is
  shared by many records or has a citation. Otherwise the record's own text field is enough, such
  as `survey.samplingProtocol`.
- **`-provenance`:** a row in `provenance` per source (dataset name and ID, creator, provider,
  funding, citation), linked from the records that came from it. Use this when one package
  combines records from several sources. A single-source dataset says this in its metadata.
- **`-usage-policy`:** a row in `usage-policy` per set of rights (`license`, `rightsHolder`,
  `credit` and so on), linked from the records it applies to. Use it when rights differ within the
  package; `media.license` is enough for a single licence per image. Never assume a licence.
- **`-media`:** the subject of a media item. `subjectPart` and `subjectOrientation` say what part
  and from which side, when recorded. A media item can show several records: one row each.
- **`-assertion`:** see `assertions.md`. Pick the table of the thing the value is about.

## Notes from the schemas

- `event-usage-policy` is described as applying "to a dwc:MaterialEntity", but it links an event.
  It is a slip in the schema text: the link says what it applies to.
- `nucleotide-analysis-assertion` is described as "about a dwc:NucleotideSequence", but it links a
  nucleotide analysis. Put values about the analysis there, such as a quality score of a run;
  `nucleotide-sequence` has no assertion table.

## How these are tested

A test builds one row in each of the 81 tables, each linked to the rows it can point to, then
validates, packages and checks it (`AllTables` in `tests/test_dwcdp.py`). That shows the tool
handles every table. It doesn't show how to model any data with them: that is what the recipes and
their worked examples are for.

## Sources

- DwC-DP 1.0 table schemas (the vendored copies): every table named above, its description, fields,
  keys and examples.
