-- Fungus finds with associated trees (made up): Darwin Core Archive -> DwC-DP 1.0.
-- Load first: load-dwca on this folder (src_dwca_occurrence).
-- The choices marked "agreed" are the data holder's; see references/interactions.md.
--
-- Agreed:
--   * associatedTaxa is the tree the fungus was found with, at the find, so it is an observed
--     interaction: the tree is an occurrence in the same event, with its own identification;
--   * the fungus acts, so it is the subject; the tree is the related occurrence;
--   * the type comes from the substrate: soil -> 'mycorrhizal symbiont of', dead wood ->
--     'saprophyte of', bark of living trees -> 'parasite of'. Any other substrate says nothing
--     about the tree, so the type stays empty and the verbatim value is the description.

DELETE FROM organism_interaction;
DELETE FROM identification;
DELETE FROM occurrence;
DELETE FROM event;

-- One event per find.
INSERT INTO event (event_pk, eventCategory, eventDate, locality, decimalLatitude, decimalLongitude,
                   geodeticDatum, recordedBy)
SELECT 'ev:' || occurrenceID, 'occurrence', eventDate, locality, CAST(decimalLatitude AS DOUBLE),
       CAST(decimalLongitude AS DOUBLE), geodeticDatum, recordedBy
FROM src_dwca_occurrence;

-- The finds, with their substrate (a dedicated field).
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus, substrate)
SELECT occurrenceID, occurrenceID, 'ev:' || occurrenceID, 'detected',
       json_extract_string(dynamicProperties, '$.Substrate')
FROM src_dwca_occurrence;

-- The associated trees: one occurrence each, in the find's event. They have no identifier of
-- their own, so occurrenceID stays empty.
INSERT INTO occurrence (occurrence_pk, event_fk, occurrenceStatus)
SELECT occurrenceID || ':associated', 'ev:' || occurrenceID, 'detected'
FROM src_dwca_occurrence WHERE nullif(associatedTaxa, '') IS NOT NULL;

-- Names, in identification: the fungus as in the archive, the tree as the genus in brackets,
-- with the value as written in verbatimIdentification and the Danish name as vernacularName.
INSERT INTO identification (identification_pk, occurrence_fk, isAcceptedIdentification, scientificName)
SELECT occurrenceID || ':id', occurrenceID, true, scientificName FROM src_dwca_occurrence;

INSERT INTO identification (identification_pk, occurrence_fk, verbatimIdentification,
                            isAcceptedIdentification, scientificName, vernacularName)
SELECT occurrenceID || ':associated:id', occurrenceID || ':associated', associatedTaxa, true,
       regexp_extract(associatedTaxa, '\(([^()]+)\)', 1),
       trim(regexp_extract(associatedTaxa, '^([^(]+)\(', 1))
FROM src_dwca_occurrence WHERE nullif(associatedTaxa, '') IS NOT NULL;

-- The interactions: fungus (subject) and tree (related), in the find's event.
INSERT INTO organism_interaction (organismInteraction_pk, event_fk, organismInteractionDescription,
                                  subjectOccurrence_fk, organismInteractionType, relatedOccurrence_fk)
SELECT occurrenceID || ':associated', 'ev:' || occurrenceID, associatedTaxa, occurrenceID,
       CASE json_extract_string(dynamicProperties, '$.Substrate')
            WHEN 'soil' THEN 'mycorrhizal symbiont of'
            WHEN 'dead wood (including bark)' THEN 'saprophyte of'
            WHEN 'bark of living trees' THEN 'parasite of'
       END,
       occurrenceID || ':associated'
FROM src_dwca_occurrence WHERE nullif(associatedTaxa, '') IS NOT NULL;
