-- A Malaise trap survey (made up) whose catches are kept, sorted for vouchers and metabarcoded.
-- Load first: catches.csv, vouchers.csv, extracts.csv, marker.csv, otu_table.tsv and taxonomy.tsv
-- as src_catches, src_vouchers, src_extracts, src_marker, src_otu_table and src_taxonomy.
-- The choices marked "agreed" are the data holder's; see references/recipes/survey.md.

DELETE FROM identification;
DELETE FROM nucleotide_analysis;
DELETE FROM nucleotide_sequence;
DELETE FROM molecular_protocol;
DELETE FROM material;
DELETE FROM occurrence;
DELETE FROM survey;
DELETE FROM event;

-- One event per catch: the trap's place, from when it was set to when it was emptied.
-- Agreed: eventCategory 'survey', eventType 'Sample' (GBIF's concept).
INSERT INTO event (event_pk, eventID, eventCategory, eventType, eventDate, locality, habitat,
                   decimalLatitude, decimalLongitude, recordedBy)
SELECT catch, catch, 'survey', 'Sample', set || '/' || collected, site, habitat,
       CAST(lat AS DOUBLE), CAST(lon AS DOUBLE), collector
FROM src_catches;

-- Each catch is a survey: a Malaise trap for the trap's days. It says that material was kept and
-- vouchers taken. Agreed: the effort is the days between setting and emptying the trap, in
-- 'trap-days'. Left empty, because the data don't say: voucherInstitutions, and anything about
-- absences or completeness.
INSERT INTO survey (survey_pk, surveyID, event_fk, samplingProtocol, isSamplingEffortReported,
                    samplingEffortValue, samplingEffortUnit, hasMaterialSamples, materialSampleTypes,
                    hasVouchers)
SELECT 'survey:' || catch, 'survey:' || catch, catch, 'Malaise trap', true,
       date_diff('day', CAST(set AS DATE), CAST(collected AS DATE)), 'trap-days',
       true, 'bulk sample in ethanol',
       EXISTS (SELECT 1 FROM src_vouchers v WHERE v.catch = c.catch)
FROM src_catches c;

-- The catch itself, kept as a bulk sample.
INSERT INTO material (materialEntity_pk, materialEntityID, collectionEvent_fk, materialEntityType,
                      preparations, disposition)
SELECT catch, catch, catch, 'Environmental sample', preservation, disposition
FROM src_catches;

-- The vouchers sorted out of the catches. Agreed: a voucher is part of its catch
-- (isPartOfMaterialEntity_fk), and the evidence for an occurrence in that catch's event.
INSERT INTO occurrence (occurrence_pk, occurrenceID, event_fk, occurrenceStatus, sex,
                        organismQuantity, organismQuantityType)
SELECT voucher || ':occurrence', voucher || ':occurrence', catch, 'detected', sex, '1', 'individuals'
FROM src_vouchers;

INSERT INTO material (materialEntity_pk, materialEntityID, catalogNumber, isPartOfMaterialEntity_fk,
                      evidenceForOccurrence_fk, materialEntityCategory, preparations)
SELECT voucher, voucher, voucher, catch, voucher || ':occurrence', 'preserved', preparation
FROM src_vouchers;

INSERT INTO identification (identification_pk, identificationID, materialEntity_fk, isAcceptedIdentification,
                            scientificName, taxonRank, identifiedBy)
SELECT voucher || ':id', voucher || ':id', voucher, true, species, 'species', determiner
FROM src_vouchers;

-- The DNA extract made from each catch's ethanol, derived from the catch.
INSERT INTO material (materialEntity_pk, materialEntityID, derivedFromMaterialEntity_fk, materialEntityCategory,
                      materialDescription, materialEntityRemarks)
SELECT extract, extract, catch, 'DNA extract', method, 'extracted ' || extracted
FROM src_extracts;

-- The COI run, as in the eDNA recipe.
INSERT INTO molecular_protocol (molecularProtocol_pk, molecularProtocolID, assayType, target_gene,
                                pcr_primer_name_forward, pcr_primer_forward, pcr_primer_name_reverse,
                                pcr_primer_reverse, pcr_primer_reference, otu_db)
SELECT marker, marker, 'metabarcoding', target_gene, fwd_name, fwd, rev_name, rev, primer_reference, reference_db
FROM src_marker;

INSERT INTO nucleotide_sequence (nucleotideSequence_pk, nucleotideSequenceID, sequence)
SELECT 'COI_' || asv, 'COI_' || asv, sequence FROM src_taxonomy;

CREATE OR REPLACE TEMP TABLE reads AS
SELECT asv, catch, CAST(reads AS BIGINT) AS reads
FROM (UNPIVOT src_otu_table ON COLUMNS(* EXCLUDE asv) INTO NAME catch VALUE reads);

INSERT INTO nucleotide_analysis (nucleotideAnalysis_pk, nucleotideAnalysisID, event_fk, materialEntity_fk,
                                 molecularProtocol_fk, nucleotideSequence_fk, readCount, processedTotalReadCount)
SELECT r.catch || ':COI_' || r.asv, r.catch || ':COI_' || r.asv, r.catch, x.extract, 'COI', 'COI_' || r.asv,
       r.reads, sum(r.reads) OVER (PARTITION BY r.catch)
FROM reads r JOIN src_extracts x ON x.catch = r.catch
WHERE r.reads > 0;

INSERT INTO identification (identification_pk, identificationID, nucleotideSequence_fk, identificationType,
                            scientificName, taxonRank, kingdom, phylum, class, "order", family, genus)
SELECT 'id:COI_' || asv, 'id:COI_' || asv, 'COI_' || asv, 'nucleotideAnalysis',
       coalesce(nullif(species, ''), nullif(genus, ''), family),
       CASE WHEN nullif(species, '') IS NOT NULL THEN 'species'
            WHEN nullif(genus, '') IS NOT NULL THEN 'genus' ELSE 'family' END,
       kingdom, phylum, class, "order", family, nullif(genus, '')
FROM src_taxonomy;
