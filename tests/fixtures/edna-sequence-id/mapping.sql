-- Names for metabarcoding sequences from a sequence matching tool (made up), in the layout of the
-- export of GBIF's sequence ID tool. Load first:
--   load sequence_id.csv --unwrap   (every line of the export is wrapped in quotes once more)
--   load ranks.csv                  (the rank of every name in the classifications)
-- See references/recipes/edna.md, "Names from a sequence matching tool".
--
-- Agreed with the data holder:
--   * the most specific name each match type supports: exact, the most specific name; ambiguous and
--     close, the genus at most; weak, the order at most from 85 % identity, and no name below it;
--     no match, no name;
--   * ranks are read from ranks.csv, never from a name's position in the classification, which
--     leaves out ranks without a name (asv4 has no order);
--   * the BOLD BIN is kept in verbatimIdentification with the classification, not as the name;
--   * human DNA (asv6) is contamination: its sequence and name stay out of the package;
--   * a sequence without a name is still published.

DELETE FROM identification;
DELETE FROM protocol;
DELETE FROM nucleotide_sequence;

CREATE OR REPLACE TEMP TABLE matches AS
SELECT * FROM src_sequence_id WHERE classification IS NULL OR classification NOT LIKE '%\_Homo\_%' ESCAPE '\';

INSERT INTO nucleotide_sequence (nucleotideSequence_pk, nucleotideSequenceID, sequence)
SELECT occurrenceId, occurrenceId, sequence FROM matches;

-- How the names were given: the tool, its match types and the agreed rule.
INSERT INTO protocol (protocol_pk, protocolType, protocolName, protocolDescription)
VALUES ('sequence-id', 'identification', 'GBIF sequence ID tool, COI',
        'Each sequence matched against the COI reference database of GBIF''s sequence ID tool. Named by match type: exact (identity of 99 % or more), the most specific name; ambiguous and close (97 % or more), the genus at most; weak, the order at most from 85 % identity, and no name below it.');

-- Every name in a classification with its rank, from ranks.csv.
CREATE OR REPLACE TEMP TABLE ranked AS
WITH parts AS (
  SELECT occurrenceId, unnest(string_split(classification, '_')) AS name FROM matches WHERE classification IS NOT NULL
)
SELECT p.occurrenceId, p.name, r.rank,
       CASE r.rank WHEN 'kingdom' THEN 1 WHEN 'phylum' THEN 2 WHEN 'class' THEN 3 WHEN 'order' THEN 4
                   WHEN 'family' THEN 5 WHEN 'genus' THEN 6 WHEN 'species' THEN 7 END AS level
FROM parts p JOIN src_ranks r ON r.name = p.name;

-- The most specific rank each match supports, by the agreed rule.
CREATE OR REPLACE TEMP TABLE allowed AS
SELECT occurrenceId, matchType, identity,
       CASE WHEN matchType = 'BLAST_EXACT_MATCH' THEN 7
            WHEN matchType IN ('BLAST_AMBIGUOUS_MATCH', 'BLAST_CLOSE_MATCH') THEN 6
            WHEN matchType = 'BLAST_WEAK_MATCH' AND CAST(identity AS DOUBLE) >= 85 THEN 4
            ELSE 0 END AS level
FROM matches;

CREATE OR REPLACE TEMP TABLE named AS
SELECT a.occurrenceId, a.matchType, a.identity,
       arg_max(r.name, r.level) AS name, arg_max(r.rank, r.level) AS rank,
       max(r.name) FILTER (WHERE r.rank = 'kingdom') AS kingdom,
       max(r.name) FILTER (WHERE r.rank = 'phylum') AS phylum,
       max(r.name) FILTER (WHERE r.rank = 'class') AS class,
       max(r.name) FILTER (WHERE r.rank = 'order') AS "order",
       max(r.name) FILTER (WHERE r.rank = 'family') AS family,
       max(r.name) FILTER (WHERE r.rank = 'genus') AS genus
FROM allowed a JOIN ranked r ON r.occurrenceId = a.occurrenceId AND r.level <= a.level
GROUP BY ALL;

INSERT INTO identification (identification_pk, identificationID, nucleotideSequence_fk, identificationType,
                            identificationProtocol_fk, isAcceptedIdentification, verbatimIdentification,
                            identificationRemarks, scientificName, taxonRank,
                            kingdom, phylum, class, "order", family, genus)
SELECT 'id:' || n.occurrenceId, 'id:' || n.occurrenceId, n.occurrenceId, 'nucleotideAnalysis', 'sequence-id', true,
       m.scientificName || ' (' || m.classification || ')',
       n.matchType || ', ' || n.identity || ' % identity; named at ' || n.rank || ' by the agreed rule',
       n.name, n.rank, n.kingdom, n.phylum, n.class, n."order", n.family, n.genus
FROM named n JOIN matches m ON m.occurrenceId = n.occurrenceId;
