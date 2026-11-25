Made up for testing: names for seven COI sequences from a sequence matching tool.

- `sequence_id.csv`: in the layout of an export of GBIF's sequence ID tool seen in a test run
  (columns `occurrenceId` … `sequence`), with every line wrapped in quotes once more. Sequences,
  BINs, identities and scores are invented. It has one of each match type, a weak match to a sponge,
  a human sequence, and a classification without an order.
- `ranks.csv`: the rank of every name in the classifications, standing in for a ranked taxonomy of
  the reference database.

The match types and their thresholds (99 % and 97 % identity) are those of GBIF's sequence ID tool
(gbif/gbif-web, `packages/graphql-api/src/api-utils/vsearch.ctrl.js` and
`src/helpers/vsearch/vsearchParser.js`, Apache-2.0).
