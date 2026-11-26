-- A beetle collection (made up): specimens, their determinations, and a tissue sample.
-- Load first: specimens.csv, determinations.csv, tissues.csv as src_specimens, src_determinations,
-- src_tissues. The choices marked "agreed" are the data holder's; see references/recipes/specimens.md.

DELETE FROM material_assertion;
DELETE FROM material_agent_role;
DELETE FROM agent;
DELETE FROM identification_taxon;
DELETE FROM identification;
DELETE FROM material;
DELETE FROM occurrence;
DELETE FROM event;

-- One collecting event per field number: the place, date and collector are written once, not
-- repeated on every specimen.
INSERT INTO event (event_pk, eventID, fieldNumber, eventCategory, eventDate, locality, country,
                   decimalLatitude, decimalLongitude, recordedBy)
SELECT DISTINCT fieldNumber, fieldNumber, fieldNumber, 'material collection', collected, locality,
       country, CAST(lat AS DOUBLE), CAST(lon AS DOUBLE), collector
FROM src_specimens;

-- Agreed: each specimen is the evidence of an occurrence, which holds the organisms' state at
-- collection (sex) and how many there were.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus, sex,
                        organismQuantity, organismQuantityType)
SELECT catalogNumber || ':occurrence', catalogNumber || ':occurrence', fieldNumber, 'detected',
       nullif(sex, ''), count, 'individuals'
FROM src_specimens;

-- Where the material is kept. The export doesn't say, so the data holder was asked (SKILL.md,
-- Stage 3, "Institution and collection"). Their answer: everything is in the care of institution
-- NHMD, which also owns it; the pinned specimens are in collection COL and the tissue in collection
-- TIS. institutionID and collectionID stay empty: they would come from a GRSciColl lookup the data
-- holder agrees to (grscicoll), which this example doesn't make.
CREATE OR REPLACE TEMP TABLE kept AS
SELECT * FROM (VALUES ('specimen', 'NHMD', 'COL'), ('tissue', 'NHMD', 'TIS')) AS k(kind, institutionCode, collectionCode);

-- The specimens. Agreed: the catalogue number is the identifier (the collection has no URIs), and
-- materialEntityCategory 'preserved'.
INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, institutionCode, collectionCode,
                      collectionEvent_fk, evidenceForOccurrence_fk, collectedBy, preparations,
                      materialEntityCategory, verbatimLabel)
SELECT s.catalogNumber, s.catalogNumber, s.catalogNumber, k.institutionCode, k.collectionCode,
       s.fieldNumber, s.catalogNumber || ':occurrence', s.collector, s.preparation, 'preserved', s.label
FROM src_specimens s, kept k WHERE k.kind = 'specimen';

-- The tissue sample, derived from a specimen. Agreed: materialEntityCategory 'tissue'.
INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, institutionCode, collectionCode,
                      derivedFromMaterialEntity_fk, preparations, materialEntityCategory)
SELECT t.tissueNumber, t.tissueNumber, t.tissueNumber, k.institutionCode, k.collectionCode,
       t.catalogNumber, t.preparation, 'tissue'
FROM src_tissues t, kept k WHERE k.kind = 'tissue';

-- Who took it and when, as a role of a person for the derived material (material-agent-role,
-- with the date in agentRoleDate). Agreed: the role is called 'sampled by'. No derivation event is
-- needed: derivedFromMaterialEntity_fk already says what it was derived from.
INSERT INTO agent (agent_pk, agentType, preferredAgentName)
SELECT DISTINCT lower(replace(taken_by, ' ', '-')), 'person', taken_by FROM src_tissues WHERE nullif(taken_by, '') IS NOT NULL
  AND lower(replace(taken_by, ' ', '-')) NOT IN (SELECT agent_pk FROM agent);

INSERT INTO material_agent_role (materialEntity_fk, agent_fk, agentRole, agentRoleOrder, agentRoleDate)
SELECT tissueNumber, lower(replace(taken_by, ' ', '-')), 'sampled by', 1, taken
FROM src_tissues WHERE nullif(taken_by, '') IS NOT NULL;


-- Every determination, of the specimen, with the current one marked. The name as written stays in
-- verbatimIdentification, and the author in scientificNameAuthorship.
-- Qualified names ("cf.", "aff."): agreed with the data holder that in their records the qualifier
-- always stands before the species epithet and doubts only the species. So scientificName is the
-- genus they are sure of, taxonFormula says how the name is qualified, and the named species is
-- taxon A in identification_taxon (see the recipe).
INSERT INTO identification (identification_pk, identificationID, materialEntity_fk,
                            isAcceptedIdentification, verbatimIdentification, scientificName,
                            scientificNameAuthorship, taxonRank, taxonFormula, identifiedBy,
                            dateIdentified, typeStatus)
SELECT catalogNumber || ':' || date, catalogNumber || ':' || date, catalogNumber,
       current = 'yes',
       name,
       CASE WHEN qualifier IS NULL THEN name ELSE split_part(name, ' ', 1) END,
       CASE WHEN qualifier IS NULL THEN nullif(author, '') END,
       CASE WHEN qualifier IS NULL THEN 'species' ELSE 'genus' END,
       CASE WHEN qualifier IS NOT NULL THEN 'A ' || qualifier END,
       determiner, date, nullif(typeStatus, '')
FROM (SELECT *, CASE WHEN split_part(name, ' ', 2) IN ('cf.', 'aff.') THEN split_part(name, ' ', 2) END AS qualifier
      FROM src_determinations);

INSERT INTO identification_taxon (identification_fk, taxonSortOrder, scientificName, taxonRank)
SELECT catalogNumber || ':' || date, 1, split_part(name, ' ', 1) || ' ' || split_part(name, ' ', 3), 'species'
FROM src_determinations
WHERE split_part(name, ' ', 2) IN ('cf.', 'aff.');

-- Elytron length has no field of its own: an assertion about the specimen (see
-- references/assertions.md). The unit comes from the column name.
INSERT INTO material_assertion (assertionID, materialEntity_fk, verbatimAssertionType, assertionType,
                                assertionValue, assertionUnit)
SELECT catalogNumber || ':elytron length', catalogNumber, 'elytra_length_mm', 'elytron length', elytra_length_mm, 'mm'
FROM src_specimens
WHERE elytra_length_mm IS NOT NULL;

-- GBIF takes an occurrence's name from the accepted identification that points to it (SKILL.md,
-- "Occurrences for GBIF"), so the identification of each specimen also points to the occurrence it
-- is evidence for.
UPDATE identification SET occurrence_fk = m.evidenceForOccurrence_fk
FROM material m
WHERE identification.materialEntity_fk = m.materialEntity_pk AND m.evidenceForOccurrence_fk IS NOT NULL;
