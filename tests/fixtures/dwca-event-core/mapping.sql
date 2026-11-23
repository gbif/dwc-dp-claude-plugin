-- An Event-core Darwin Core Archive (made up), translated to DwC-DP.
-- Load first: dwcdp.py load-dwca <this folder>, which stages src_dwca_event, src_dwca_occurrence
-- and src_dwca_extendedmeasurementorfact. The choices marked "agreed" are the data holder's; see
-- references/recipes/dwca.md.

DELETE FROM occurrence_assertion;
DELETE FROM event_assertion;
DELETE FROM identification;
DELETE FROM occurrence;
DELETE FROM survey;
DELETE FROM event;

-- The events and their hierarchy (parentEventID). Agreed: the survey as a whole is the context
-- (eventCategory 'context'); each grab sample is a survey of its own (eventCategory 'survey'), since
-- the method and sample size are per sample. Water depth has dedicated fields on event, so the
-- eMoF "water depth" rows go there (agreed: the grab samples the bottom, so the sample's depth is
-- the water depth).
INSERT INTO event (event_pk, eventID, parentEvent_fk, eventCategory, eventType, eventDate, locality,
                   decimalLatitude, decimalLongitude, geodeticDatum, minimumDepthInMeters, maximumDepthInMeters)
SELECT e.eventID, e.eventID, nullif(e.parentEventID, ''),
       CASE WHEN nullif(e.parentEventID, '') IS NULL THEN 'context' ELSE 'survey' END,
       e.eventType, e.eventDate, e.locality,
       TRY_CAST(e.decimalLatitude AS DOUBLE), TRY_CAST(e.decimalLongitude AS DOUBLE), nullif(e.geodeticDatum, ''),
       CAST(d.measurementValue AS DOUBLE), CAST(d.measurementValue AS DOUBLE)
FROM src_dwca_event e
LEFT JOIN src_dwca_extendedmeasurementorfact d
       ON d.coreid = e.id AND d.measurementType = 'water depth' AND nullif(d.occurrenceID, '') IS NULL;

-- samplingProtocol and sampleSize exist only on survey in DwC-DP: one survey per sample event.
INSERT INTO survey (survey_pk, surveyID, event_fk, samplingProtocol, sampleSizeValue, sampleSizeUnit)
SELECT 'survey:' || eventID, 'survey:' || eventID, eventID, samplingProtocol,
       nullif(sampleSizeValue, ''), nullif(sampleSizeUnit, '')
FROM src_dwca_event
WHERE nullif(parentEventID, '') IS NOT NULL;

-- The occurrences of each sample. occurrenceStatus 'present' and 'absent' are deprecated in GBIF's
-- vocabulary in favour of 'detected' and 'notDetected' (dwcdp.py vocab OccurrenceStatus); agreed
-- to write those.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus, organismQuantity,
                        organismQuantityType)
SELECT occurrenceID, occurrenceID, coreid,
       CASE occurrenceStatus WHEN 'present' THEN 'detected' WHEN 'absent' THEN 'notDetected' ELSE occurrenceStatus END,
       organismQuantity, organismQuantityType
FROM src_dwca_occurrence;

INSERT INTO identification (identification_pk, identificationID, occurrence_fk, isAcceptedIdentification,
                            scientificName, taxonRank, kingdom)
SELECT occurrenceID || ':id', occurrenceID || ':id', occurrenceID, true, scientificName,
       nullif(taxonRank, ''), nullif(kingdom, '')
FROM src_dwca_occurrence;

-- The other eMoF rows as assertions: about the occurrence when the row names one (occurrenceID),
-- otherwise about the event it hangs on. measurementTypeID and measurementUnitID are IRIs, so they
-- go in assertionTypeIRI and assertionUnitIRI.
INSERT INTO event_assertion (assertionID, event_fk, assertionType, assertionTypeIRI, assertionValue,
                             assertionUnit, assertionUnitIRI)
SELECT coreid || ':' || measurementType, coreid, measurementType, nullif(measurementTypeID, ''), measurementValue,
       nullif(measurementUnit, ''), nullif(measurementUnitID, '')
FROM src_dwca_extendedmeasurementorfact
WHERE nullif(occurrenceID, '') IS NULL AND measurementType <> 'water depth';

INSERT INTO occurrence_assertion (assertionID, occurrence_fk, assertionType, assertionTypeIRI, assertionValue,
                                  assertionUnit, assertionUnitIRI)
SELECT occurrenceID || ':' || measurementType, occurrenceID, measurementType, nullif(measurementTypeID, ''),
       measurementValue, nullif(measurementUnit, ''), nullif(measurementUnitID, '')
FROM src_dwca_extendedmeasurementorfact
WHERE nullif(occurrenceID, '') IS NOT NULL;
