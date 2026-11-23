-- A beetle collection (made up): specimens, their determinations, and a tissue sample.
-- Load first: specimens.csv, determinations.csv, tissues.csv as src_specimens, src_determinations,
-- src_tissues. The choices marked "agreed" are the data holder's; see references/recipes/specimens.md.

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

-- The specimens. Agreed: the catalogue number is the identifier (the collection has no URIs), and
-- materialEntityCategory 'preserved'. institutionCode and collectionCode are not in the export,
-- so they stay empty until the data holder gives them.
INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, collectionEvent_fk,
                      evidenceForOccurrence_fk, collectedBy, preparations, materialEntityCategory,
                      verbatimLabel)
SELECT catalogNumber, catalogNumber, catalogNumber, fieldNumber, catalogNumber || ':occurrence',
       collector, preparation, 'preserved', label
FROM src_specimens;

-- The tissue sample, derived from a specimen. Agreed: materialEntityCategory 'tissue'. The date it
-- was taken stays in the remarks; see the recipe for recording it as a derivation event.
INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, derivedFromMaterialEntity_fk,
                      preparations, materialEntityCategory, materialEntityRemarks)
SELECT tissueNumber, tissueNumber, tissueNumber, catalogNumber, preparation, 'tissue',
       'taken ' || taken
FROM src_tissues;

-- Every determination, of the specimen, with the current one marked. The name as written stays in
-- verbatimIdentification, and the author in scientificNameAuthorship. Agreed: the "cf." name keeps
-- no scientificName until the data holder says how to express the qualifier (see the recipe).
INSERT INTO identification (identification_pk, identificationID, materialEntity_fk,
                            isAcceptedIdentification, verbatimIdentification, scientificName,
                            scientificNameAuthorship, identifiedBy, dateIdentified, typeStatus)
SELECT catalogNumber || ':' || date, catalogNumber || ':' || date, catalogNumber,
       current = 'yes',
       name,
       CASE WHEN name LIKE '% cf. %' THEN NULL ELSE name END,
       nullif(author, ''), determiner, date, nullif(typeStatus, '')
FROM src_determinations;
