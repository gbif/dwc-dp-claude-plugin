-- An Occurrence-core Darwin Core Archive (made up), translated to DwC-DP.
-- Load first: dwcdp.py load-dwca <this folder>, which stages src_dwca_occurrence,
-- src_dwca_multimedia and src_dwca_measurementorfact. The choices marked "agreed" are the data
-- holder's; see references/recipes/dwca.md.

DELETE FROM material_assertion;
DELETE FROM occurrence_media;
DELETE FROM media;
DELETE FROM identification;
DELETE FROM material;
DELETE FROM occurrence;
DELETE FROM event;

-- One event per record: an Occurrence core row carries its own place and time. Agreed: rows with
-- the same fieldNumber are one collecting event; the others get an event of their own.
INSERT INTO event (event_pk, eventID, fieldNumber, eventCategory, eventDate, locality, countryCode,
                   decimalLatitude, decimalLongitude, geodeticDatum, recordedBy)
SELECT DISTINCT coalesce(nullif(fieldNumber, ''), occurrenceID), coalesce(nullif(fieldNumber, ''), occurrenceID),
       nullif(fieldNumber, ''), CASE WHEN basisOfRecord = 'PreservedSpecimen' THEN 'material collection' ELSE 'occurrence' END,
       eventDate, locality, countryCode, CAST(decimalLatitude AS DOUBLE), CAST(decimalLongitude AS DOUBLE),
       geodeticDatum, recordedBy
FROM src_dwca_occurrence;

-- One occurrence per record. The archive has no occurrenceStatus; agreed: these are records of
-- organisms found, so 'detected'. individualCount has no field of its own: it is organismQuantity
-- with organismQuantityType 'individuals'.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus, sex,
                        organismQuantity, organismQuantityType)
SELECT occurrenceID, occurrenceID, coalesce(nullif(fieldNumber, ''), occurrenceID), 'detected',
       nullif(sex, ''), nullif(individualCount, ''), CASE WHEN nullif(individualCount, '') IS NOT NULL THEN 'individuals' END
FROM src_dwca_occurrence;

-- basisOfRecord has no field: in DwC-DP a specimen is a material row, an observation is not.
-- Agreed: PreservedSpecimen rows become material, the evidence for their occurrence.
INSERT INTO material (materialEntity_pk, materialEntityID, institutionCode, catalogNumber, preparations,
                      collectionEvent_fk, evidenceForOccurrence_fk, collectedBy, materialEntityCategory)
SELECT occurrenceID, occurrenceID, institutionCode, catalogNumber, preparations, fieldNumber, occurrenceID,
       recordedBy, 'preserved'
FROM src_dwca_occurrence
WHERE basisOfRecord = 'PreservedSpecimen';

-- The name, with its higher ranks: kingdom and family exist only in identification. Based on the
-- occurrence, which GBIF reads it from (SKILL.md, "Occurrences for GBIF"), and for specimens also of
-- the specimen.
INSERT INTO identification (identification_pk, identificationID, materialEntity_fk, occurrence_fk,
                            isAcceptedIdentification, scientificName, taxonRank, kingdom, family)
SELECT occurrenceID || ':id', occurrenceID || ':id',
       CASE WHEN basisOfRecord = 'PreservedSpecimen' THEN occurrenceID END,
       occurrenceID,
       true, scientificName, nullif(taxonRank, ''), nullif(kingdom, ''), nullif(family, '')
FROM src_dwca_occurrence;

-- Simple Multimedia: one media row per image, shown by the record's occurrence. dcterms:format
-- holds a MIME type string here, which in DwC-DP goes in format (formatIRI is for an IRI).
INSERT INTO media (media_pk, mediaID, mediaType, accessURI, format, license)
SELECT identifier, identifier, type, identifier, format, license FROM src_dwca_multimedia;

INSERT INTO occurrence_media (media_fk, occurrence_fk)
SELECT identifier, coreid FROM src_dwca_multimedia;

-- MeasurementOrFact rows as assertions. Agreed: body length was measured on the specimen, so it is
-- about the material. The measurement terms match the assertion terms by meaning (see the recipe).
INSERT INTO material_assertion (assertionID, materialEntity_fk, assertionType, assertionValue, assertionUnit,
                                assertionProtocols)
SELECT m.coreid || ':' || m.measurementType, m.coreid, m.measurementType, m.measurementValue,
       nullif(m.measurementUnit, ''), nullif(m.measurementMethod, '')
FROM src_dwca_measurementorfact m JOIN src_dwca_occurrence o ON o.id = m.coreid
WHERE o.basisOfRecord = 'PreservedSpecimen';
