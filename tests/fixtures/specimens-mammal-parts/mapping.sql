-- Mammal specimens kept as several pieces (made up). Load first: specimens.csv and parts.csv as
-- src_specimens and src_parts. The choices marked "agreed" are the data holder's; see
-- references/recipes/specimens.md.

DELETE FROM material_agent_role;
DELETE FROM agent;
DELETE FROM identification;
DELETE FROM material;
DELETE FROM occurrence;
DELETE FROM event;

INSERT INTO event (event_pk, eventID, fieldNumber, eventCategory, eventDate, locality,
                   decimalLatitude, decimalLongitude, recordedBy)
SELECT fieldNumber, fieldNumber, fieldNumber, 'material collection', collected, locality,
       CAST(lat AS DOUBLE), CAST(lon AS DOUBLE), collector
FROM src_specimens;

INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus, sex,
                        organismQuantity, organismQuantityType)
SELECT catalogNumber || ':occurrence', catalogNumber || ':occurrence', fieldNumber, 'detected',
       sex, '1', 'individuals'
FROM src_specimens;

-- The catalogued specimen as a whole: what the catalogue number and the determination refer to.
-- Agreed: its preparations list its pieces, so the record is complete on its own too.
INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, collectionEvent_fk,
                      evidenceForOccurrence_fk, collectedBy, materialEntityCategory, preparations)
SELECT s.catalogNumber, s.catalogNumber, s.catalogNumber, s.fieldNumber,
       s.catalogNumber || ':occurrence', s.collector, 'preserved',
       (SELECT string_agg(p.part, ' | ' ORDER BY p.partNumber) FROM src_parts p
         WHERE p.catalogNumber = s.catalogNumber AND p.kind = 'part')
FROM src_specimens s;

-- Each piece kept on its own, with its own number, preparation and disposition.
-- Agreed: skin, skull and skeleton are parts of the specimen (isPartOfMaterialEntity_fk); the
-- frozen liver is a subsample taken from it (derivedFromMaterialEntity_fk).
INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, isPartOfMaterialEntity_fk,
                      derivedFromMaterialEntity_fk, materialEntityCategory, preparations,
                      materialDescription, disposition)
SELECT partNumber, partNumber, partNumber,
       CASE WHEN kind = 'part' THEN catalogNumber END,
       CASE WHEN kind = 'subsample' THEN catalogNumber END,
       CASE WHEN kind = 'subsample' THEN 'tissue' ELSE 'preserved' END,
       preparation, part, disposition
FROM src_parts;

-- Who took it and when, as a role of a person for the derived material (material-agent-role,
-- with the date in agentRoleDate). Agreed: the role is called 'sampled by'. No derivation event is
-- needed: derivedFromMaterialEntity_fk already says what it was derived from.
INSERT INTO agent (agent_pk, agentType, preferredAgentName)
SELECT DISTINCT lower(replace(taken_by, ' ', '-')), 'person', taken_by FROM src_parts WHERE nullif(taken_by, '') IS NOT NULL
  AND lower(replace(taken_by, ' ', '-')) NOT IN (SELECT agent_pk FROM agent);

INSERT INTO material_agent_role (materialEntity_fk, agent_fk, agentRole, agentRoleOrder, agentRoleDate)
SELECT partNumber, lower(replace(taken_by, ' ', '-')), 'sampled by', 1, taken
FROM src_parts WHERE nullif(taken_by, '') IS NOT NULL;


-- The determination is of the specimen as a whole, not of each piece.
INSERT INTO identification (identification_pk, identificationID, materialEntity_fk,
                            isAcceptedIdentification, scientificName, taxonRank)
SELECT catalogNumber || ':id', catalogNumber || ':id', catalogNumber, true, species, 'species'
FROM src_specimens;
