-- Fossils and subfossils (made up): stratigraphy as recorded, radiocarbon ages, a rock sample.
-- Load first: specimens.csv, dates.csv and rocks.csv as src_specimens, src_dates, src_rocks.
-- The choices marked "agreed" are the data holder's; see references/recipes/paleo.md.

DELETE FROM geological_material;
DELETE FROM material_geological_context;
DELETE FROM geological_context;
DELETE FROM chronometric_age;
DELETE FROM protocol;
DELETE FROM identification;
DELETE FROM material;
DELETE FROM occurrence;
DELETE FROM event;

-- One collecting event per field number: a cave layer excavated on a day, a cliff visited on a day.
INSERT INTO event (event_pk, eventID, fieldNumber, eventCategory, eventDate, locality,
                   decimalLatitude, decimalLongitude, recordedBy)
SELECT DISTINCT fieldNumber, fieldNumber, fieldNumber, 'material collection', collected, locality,
       CAST(lat AS DOUBLE), CAST(lon AS DOUBLE), collector
FROM src_specimens;

-- The organism each specimen is evidence of.
INSERT INTO occurrence (occurrence_pk, event_fk, occurrenceStatus)
SELECT catalogNumber || ':occurrence', fieldNumber, 'detected' FROM src_specimens;

-- The specimens. Agreed: fossils are 'fossilized' and subfossil bone and antler 'preserved' (both
-- schema examples); the element goes in preparations.
INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, collectionEvent_fk,
                      evidenceForOccurrence_fk, collectedBy, materialEntityCategory, preparations)
SELECT catalogNumber, catalogNumber, catalogNumber, fieldNumber, catalogNumber || ':occurrence', collector,
       CASE kind WHEN 'fossil' THEN 'fossilized' ELSE 'preserved' END, element
FROM src_specimens;

INSERT INTO identification (identification_pk, identificationID, materialEntity_fk, isAcceptedIdentification,
                            scientificName)
SELECT catalogNumber || ':id', catalogNumber || ':id', catalogNumber, true, taxon FROM src_specimens;

-- Stratigraphy as the collection records it: one geological context per distinct combination.
-- The cave layer has no formation or stage, so its specimens get none (nothing is derived here).
INSERT INTO geological_context (geologicalContext_pk, formation, member, earliestAgeOrLowestStage, latestAgeOrHighestStage)
SELECT DISTINCT concat_ws(' | ', formation, member, stage), formation, member, stage, stage
FROM src_specimens WHERE nullif(formation, '') IS NOT NULL;

INSERT INTO material_geological_context (geologicalContext_fk, materialEntity_fk)
SELECT concat_ws(' | ', formation, member, stage), catalogNumber
FROM src_specimens WHERE nullif(formation, '') IS NOT NULL;

-- The rock sample: material collected on the cliff visit, and geological material with its
-- lithology and minerals. Agreed: the lithology and the minerals are both names of the material,
-- typed as such.
INSERT INTO protocol (protocol_pk, protocolType, protocolName)
SELECT DISTINCT analysis, 'mineralogical analysis', analysis FROM src_rocks
UNION ALL
SELECT DISTINCT method, 'chronometric age', method FROM src_dates
UNION ALL
SELECT DISTINCT curve, 'chronometric age conversion', curve || ' calibration curve' FROM src_dates;

INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, collectionEvent_fk, collectedBy,
                      materialEntityCategory, materialEntityType)
SELECT sampleNumber, sampleNumber, sampleNumber, fieldNumber, collector, 'non-biological', 'Macro-object'
FROM src_rocks;

INSERT INTO material_geological_context (geologicalContext_fk, materialEntity_fk)
SELECT DISTINCT concat_ws(' | ', s.formation, s.member, s.stage), r.sampleNumber
FROM src_rocks r JOIN src_specimens s USING (fieldNumber)
WHERE nullif(s.formation, '') IS NOT NULL;

INSERT INTO geological_material (materialEntity_fk, materialEntityID, geologicalMaterialNames,
                                 geologicalMaterialNameTypes, mineralogicalAnalysisProtocol,
                                 mineralogicalAnalysisProtocol_fk)
SELECT sampleNumber, sampleNumber, lithology || ' | ' || minerals, 'lithology | mineral | mineral', analysis, analysis
FROM src_rocks;

-- The radiocarbon ages. An age belongs to an event (event_fk is required, and the table has no
-- link to the material the age applies to), so both are ages of the layer's collecting event, and
-- of everything collected in it. Calibrated range in the earliest/latest fields (cal yr BP), the
-- radiocarbon age before calibration in uncalibratedChronometricAge, the curve as the conversion
-- protocol. The error is of the radiocarbon age, so chronometricAgeUncertaintyInYears, which is
-- about the calibrated ages, stays empty (agreed). materialDated says what was dated: the bone
-- FOS-1 itself (also as materialDated_fk), or charcoal that isn't in the collection, with the
-- relationship as the data holder states it.
INSERT INTO chronometric_age (chronometricAge_pk, chronometricAgeID, event_fk, verbatimChronometricAge,
                              chronometricAgeProtocol, chronometricAgeProtocol_fk, uncalibratedChronometricAge,
                              chronometricAgeConversionProtocol, chronometricAgeConversionProtocol_fk,
                              earliestChronometricAge, earliestChronometricAgeReferenceSystem,
                              latestChronometricAge, latestChronometricAgeReferenceSystem,
                              materialDated, materialDated_fk, materialDatedRelationship)
SELECT d.labNumber, d.labNumber, d.fieldNumber, d.c14Age || ' ± ' || d.c14Error || ' 14C yr BP',
       d.method, d.method, d.c14Age || ' ± ' || d.c14Error || ' 14C yr BP', d.curve, d.curve,
       d.calOldest, 'cal yr BP', d.calYoungest, 'cal yr BP',
       d.datedMaterial, nullif(d.datedCatalogNumber, ''), nullif(d.relation, '')
FROM src_dates d;

-- GBIF takes an occurrence's name from the accepted identification that points to it (SKILL.md,
-- "Occurrences for GBIF"), so the identification of each specimen also points to the occurrence it
-- is evidence for.
UPDATE identification SET occurrence_fk = m.evidenceForOccurrence_fk
FROM material m
WHERE identification.materialEntity_fk = m.materialEntity_pk AND m.evidenceForOccurrence_fk IS NOT NULL;
