-- Sedimentary ancient DNA from a dated lake core: Lake Lama, core PG1341 (von Hippel et al. 2022).
-- Load first: markers.tsv, and fungi_* and plants_* (samples, otu_table, taxonomy), each under its
-- own name (src_fungi_samples, ...).
-- See references/recipes/paleo.md.
--
-- Agreed with the data holder:
--   * depth in the core is an assertion on the slice ("depth in core", cm);
--   * the epoch is derived from the age: younger than 11,650 cal yr BP (the base of the Holocene,
--     11,700 years before AD 2000) is Holocene, older is Pleistocene.
--   * each slice has its own subsampling event under the coring event, which its age and its DNA
--     analyses point to (chronometric-age.event_fk is required, and the schema doesn't say which
--     event).
-- Chosen for this example, as the recipe proposes:
--   * one coring event; the core, its sections, the depth slices and the DNA extracts as material,
--     each section part of the core, each slice derived from its section and each extract from its
--     slice;
--   * the slice depth is the section's top plus the slice's depth within the section, both read from
--     the trnL sample IDs;
--   * the age of each slice as a chronometric age from the study's age-depth model (a protocol, cited
--     to the paper);
--   * one molecular protocol per marker, one analysis per PCR replicate and OTU with reads, the
--     replicate's total over all OTUs as processedTotalReadCount, names in identification.

DELETE FROM identification;
DELETE FROM nucleotide_analysis;
DELETE FROM nucleotide_sequence;
DELETE FROM molecular_protocol_reference;
DELETE FROM molecular_protocol;
DELETE FROM material_geological_context;
DELETE FROM geological_context;
DELETE FROM chronometric_age;
DELETE FROM protocol_reference;
DELETE FROM protocol;
DELETE FROM bibliographic_resource;
DELETE FROM material_assertion;
DELETE FROM material;
DELETE FROM event;

-- The replicates of both markers, with their extract, age and the depths read from the IDs.
CREATE OR REPLACE TEMP TABLE replicates AS
SELECT 'fungi' AS marker, * FROM src_fungi_samples
UNION ALL BY NAME
SELECT 'plants' AS marker, * FROM src_plants_samples;

-- One row per depth slice, from the trnL IDs: section PG1341-11 spans 1783-1883 cm, and the slice
-- lies 37-38 cm into it.
CREATE OR REPLACE TEMP TABLE slices AS
SELECT DISTINCT materialSampleID AS extract, fieldNumber AS core, age,
       regexp_extract(id, '(PG1341-\d+)_', 1) AS section,
       CAST(regexp_extract(id, '_(\d+)-(\d+)cm_(\d+)-(\d+)cm', 1) AS INTEGER) AS section_top,
       CAST(regexp_extract(id, '_(\d+)-(\d+)cm_(\d+)-(\d+)cm', 2) AS INTEGER) AS section_bottom,
       CAST(regexp_extract(id, '_(\d+)-(\d+)cm_(\d+)-(\d+)cm', 1) AS INTEGER)
         + CAST(regexp_extract(id, '_(\d+)-(\d+)cm_(\d+)-(\d+)cm', 3) AS INTEGER) AS top,
       CAST(regexp_extract(id, '_(\d+)-(\d+)cm_(\d+)-(\d+)cm', 1) AS INTEGER)
         + CAST(regexp_extract(id, '_(\d+)-(\d+)cm_(\d+)-(\d+)cm', 4) AS INTEGER) AS bottom
FROM src_plants_samples;

-- 1. The coring event: the lake, the year, and the lake's coordinates (the core position isn't
--    given, as georeferenceRemarks says).
INSERT INTO event (event_pk, eventID, eventCategory, eventType, eventDate, locality, countryCode,
                   decimalLatitude, decimalLongitude, georeferenceRemarks)
SELECT DISTINCT 'coring:' || fieldNumber, NULL, 'material collection', 'Sample', eventDate, locality, 'RU',
       CAST(decimalLatitude AS DOUBLE), CAST(decimalLongitude AS DOUBLE), georeferenceRemarks
FROM replicates;

-- The subsampling of each slice, under the coring event. When it was done isn't recorded, so
-- eventDate stays empty.
INSERT INTO event (event_pk, parentEvent_fk, eventCategory, eventType, eventRemarks)
SELECT 'subsample:' || core || ':' || top || '-' || bottom, 'coring:' || core, 'material collection', 'SubSample',
       'sediment slice ' || top || '-' || bottom || ' cm of core ' || core
FROM slices;

-- 2. The material: core, sections, slices and extracts.
INSERT INTO material (materialEntity_pk, materialEntityID, collectionEvent_fk, materialEntityType, materialDescription)
SELECT DISTINCT core, core, 'coring:' || core, 'Core', 'lake sediment core' FROM slices;

INSERT INTO material (materialEntity_pk, materialEntityID, isPartOfMaterialEntity_fk, materialDescription)
SELECT DISTINCT section, section, core, 'core section' FROM slices;

INSERT INTO material (materialEntity_pk, collectionEvent_fk, derivedFromMaterialEntity_fk, materialDescription)
SELECT core || ':' || top || '-' || bottom, 'subsample:' || core || ':' || top || '-' || bottom, section,
       'sediment slice, ' || top || '-' || bottom || ' cm'
FROM slices;

INSERT INTO material (materialEntity_pk, materialEntityID, derivedFromMaterialEntity_fk, materialEntityCategory)
SELECT extract, extract, core || ':' || top || '-' || bottom, 'DNA extract' FROM slices;

-- Depth in the core, for the sections and the slices (agreed: an assertion; material has no depth
-- field, and the event's depth fields are depths below the water or ground surface).
INSERT INTO material_assertion (assertionID, materialEntity_fk, assertionType, assertionValue, assertionUnit, assertionRemarks)
SELECT DISTINCT section || ':depth', section, 'depth in core', section_top || '-' || section_bottom, 'cm',
       'from the sample IDs'
FROM slices
UNION ALL
SELECT core || ':' || top || '-' || bottom || ':depth', core || ':' || top || '-' || bottom, 'depth in core',
       top || '-' || bottom, 'cm', 'section top plus the depth within the section, from the sample IDs'
FROM slices;

-- 3. The age of each slice, from the study's age-depth model.
INSERT INTO bibliographic_resource (reference_pk, referenceType, bibliographicCitation, bibliographicIdentifier,
                                    bibliographicIdentifierType, title, issued, volume, pages)
VALUES ('vonHippel2022', 'article',
        'von Hippel B, Stoof-Leichsenring KR, Schulte L, Seeber P, Epp LS, Biskaborn BK, Diekmann B, Melles M, Pestryakova L, Herzschuh U (2022). Long-term fungus-plant covariation from multi-site sedimentary ancient DNA metabarcoding. Quaternary Science Reviews 295: 107758.',
        '10.1016/j.quascirev.2022.107758', 'DOI',
        'Long-term fungus-plant covariation from multi-site sedimentary ancient DNA metabarcoding',
        '2022', '295', '107758');

INSERT INTO protocol (protocol_pk, protocolType, protocolName, protocolReferences)
VALUES ('age-depth-model', 'chronometric age', 'age-depth model of the core',
        'von Hippel et al. (2022), https://doi.org/10.1016/j.quascirev.2022.107758');

INSERT INTO protocol_reference (protocol_fk, reference_fk, relationshipType)
VALUES ('age-depth-model', 'vonHippel2022', 'cited in');

INSERT INTO chronometric_age (chronometricAge_pk, event_fk, verbatimChronometricAge, chronometricAgeProtocol,
                              chronometricAgeProtocol_fk, earliestChronometricAge, earliestChronometricAgeReferenceSystem,
                              latestChronometricAge, latestChronometricAgeReferenceSystem, materialDated_fk)
SELECT 'age:' || core || ':' || top || '-' || bottom, 'subsample:' || core || ':' || top || '-' || bottom, age || ' cal yr BP', 'age-depth model', 'age-depth-model',
       age, 'cal yr BP', age, 'cal yr BP', core || ':' || top || '-' || bottom
FROM slices;

-- 4. The epoch of each slice, derived from its age (agreed rule; GBIF's GeoTime concepts).
INSERT INTO geological_context (geologicalContext_pk, earliestEpochOrLowestSeries, latestEpochOrHighestSeries)
VALUES ('Holocene', 'Holocene', 'Holocene'), ('Pleistocene', 'Pleistocene', 'Pleistocene');

INSERT INTO material_geological_context (geologicalContext_fk, materialEntity_fk)
SELECT CASE WHEN CAST(age AS INTEGER) < 11650 THEN 'Holocene' ELSE 'Pleistocene' END, core || ':' || top || '-' || bottom
FROM slices;

-- 5. DNA: one protocol per marker, the OTUs, and one analysis per replicate and OTU with reads.
INSERT INTO molecular_protocol (molecularProtocol_pk, molecularProtocolID, assayType, target_gene,
                                pcr_primer_name_forward, pcr_primer_name_reverse, pcr_primer_reference,
                                otu_db, seq_meth)
SELECT marker, marker, 'metabarcoding', target_gene, pcr_primer_name_forward, pcr_primer_name_reverse,
       pcr_primer_reference, otu_db, seq_meth
FROM src_markers;

INSERT INTO molecular_protocol_reference (molecularProtocol_fk, reference_fk, relationshipType)
SELECT marker, 'vonHippel2022', 'cited in' FROM src_markers;

INSERT INTO nucleotide_sequence (nucleotideSequence_pk, nucleotideSequenceID, sequence)
SELECT id, id, DNA_sequence FROM src_fungi_taxonomy
UNION ALL
SELECT id, id, DNA_sequence FROM src_plants_taxonomy;

CREATE OR REPLACE TEMP TABLE reads AS
SELECT 'fungi' AS marker, id AS otu, replicate, CAST(reads AS BIGINT) AS reads
FROM (UNPIVOT src_fungi_otu_table ON COLUMNS(* EXCLUDE id) INTO NAME replicate VALUE reads)
UNION ALL
SELECT 'plants', id, replicate, CAST(reads AS BIGINT)
FROM (UNPIVOT src_plants_otu_table ON COLUMNS(* EXCLUDE id) INTO NAME replicate VALUE reads);

INSERT INTO nucleotide_analysis (nucleotideAnalysis_pk, nucleotideAnalysisID, event_fk, materialEntity_fk,
                                 molecularProtocol_fk, nucleotideSequence_fk, readCount, processedTotalReadCount)
SELECT r.replicate || ':' || r.otu, r.replicate || ':' || r.otu,
       'subsample:' || x.core || ':' || x.top || '-' || x.bottom, s.materialSampleID,
       r.marker, r.otu, r.reads, CAST(s.total_reads AS BIGINT)
FROM reads r JOIN replicates s ON s.id = r.replicate AND s.marker = r.marker
     JOIN slices x ON x.extract = s.materialSampleID
WHERE r.reads > 0;

-- 6. One identification per OTU, based on its sequence, with the match as its remarks.
INSERT INTO identification (identification_pk, identificationID, nucleotideSequence_fk, identificationType,
                            scientificName, taxonRank, "order", family, genus, identificationRemarks)
SELECT 'id:' || id, 'id:' || id, id, 'nucleotideAnalysis', scientificName, nullif(taxonRank, ''),
       nullif("order", ''), nullif(family, ''), nullif(genus, ''), identificationRemarks
FROM (SELECT * FROM src_fungi_taxonomy UNION ALL BY NAME SELECT * FROM src_plants_taxonomy);
