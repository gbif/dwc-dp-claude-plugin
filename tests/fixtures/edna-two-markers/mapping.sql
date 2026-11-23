-- eDNA with two markers on the same samples (made up): 12S for fish and COI for invertebrates.
-- Load first: samples.csv and markers.csv as src_samples and src_markers, and the four tables with
-- --as: otu_12s, taxonomy_12s, otu_coi, taxonomy_coi (load adds src_).
-- The choices marked "agreed" are the data holder's; see references/recipes/edna.md.

DELETE FROM identification;
DELETE FROM nucleotide_analysis;
DELETE FROM nucleotide_sequence;
DELETE FROM molecular_protocol;
DELETE FROM material;
DELETE FROM event;

-- One sampling event per site and date. The field blank was taken on the same visit as S1, so they
-- share it. Agreed: eventCategory 'material collection', eventType 'Sample' (GBIF's concept).
INSERT INTO event (event_pk, eventID, eventCategory, eventType, eventDate, locality,
                   decimalLatitude, decimalLongitude)
SELECT DISTINCT site || ' ' || date, site || ' ' || date, 'material collection', 'Sample', date, site,
       CAST(lat AS DOUBLE), CAST(lon AS DOUBLE)
FROM src_samples;

-- One material row per water sample and per blank. Agreed: materialEntityType
-- 'Environmental sample' (a schema example); the blank is marked as a negative control in its
-- remarks.
INSERT INTO material (materialEntity_pk, materialEntityID, collectionEvent_fk, materialEntityType,
                      materialEntityRemarks)
SELECT sample, sample, site || ' ' || date, 'Environmental sample',
       CASE WHEN type = 'field blank' THEN 'field blank (negative control)' END
FROM src_samples;

-- One molecular protocol per marker: the assay, its primers and the reference database.
-- Agreed: target_gene written as GBIF's concept name (GBIF reads "12S rRNA" as
-- SSU_rRNA_12S_mitochondrial only by a hidden label). The reference database goes in otu_db, as
-- the MDT does; see the recipe about this term.
INSERT INTO molecular_protocol (molecularProtocol_pk, molecularProtocolID, assayType, target_gene,
                                pcr_primer_name_forward, pcr_primer_forward,
                                pcr_primer_name_reverse, pcr_primer_reverse,
                                pcr_primer_reference, otu_db, samp_vol_we_dna_ext)
SELECT marker, marker, 'metabarcoding',
       CASE target_gene WHEN '12S rRNA' THEN 'SSU_rRNA_12S_mitochondrial' ELSE target_gene END,
       fwd_name, fwd, rev_name, rev, primer_reference, reference_db,
       (SELECT DISTINCT volume_ml FROM src_samples) || ' ml'
FROM src_markers;

-- The ASVs of both markers.
INSERT INTO nucleotide_sequence (nucleotideSequence_pk, nucleotideSequenceID, sequence)
SELECT asv, asv, sequence FROM src_taxonomy_12s
UNION ALL
SELECT asv, asv, sequence FROM src_taxonomy_coi;

-- One analysis per sample, marker and ASV with reads; a 0 in an OTU table gets no row (agreed).
-- processedTotalReadCount is the sample's total for that marker: each marker is its own library,
-- so totals are per sample and marker (agreed; see the recipe).
CREATE OR REPLACE TEMP TABLE reads AS
SELECT '12S' AS marker, asv, sample, CAST(reads AS BIGINT) AS reads
FROM (UNPIVOT src_otu_12s ON COLUMNS(* EXCLUDE asv) INTO NAME sample VALUE reads)
UNION ALL
SELECT 'COI', asv, sample, CAST(reads AS BIGINT)
FROM (UNPIVOT src_otu_coi ON COLUMNS(* EXCLUDE asv) INTO NAME sample VALUE reads);

INSERT INTO nucleotide_analysis (nucleotideAnalysis_pk, nucleotideAnalysisID, event_fk, materialEntity_fk,
                                 molecularProtocol_fk, nucleotideSequence_fk, readCount,
                                 processedTotalReadCount)
SELECT r.sample || ':' || r.asv, r.sample || ':' || r.asv, s.site || ' ' || s.date, r.sample,
       r.marker, r.asv, r.reads,
       sum(r.reads) OVER (PARTITION BY r.sample, r.marker)
FROM reads r JOIN src_samples s ON s.sample = r.sample
WHERE r.reads > 0;

-- One identification per ASV, based on its sequence, at the lowest rank the assignment reached.
INSERT INTO identification (identification_pk, identificationID, nucleotideSequence_fk, identificationType,
                            scientificName, taxonRank, kingdom, phylum, class, "order", family, genus)
SELECT 'id:' || asv, 'id:' || asv, asv, 'nucleotideAnalysis',
       coalesce(nullif(species, ''), nullif(genus, ''), family),
       CASE WHEN nullif(species, '') IS NOT NULL THEN 'species'
            WHEN nullif(genus, '') IS NOT NULL THEN 'genus' ELSE 'family' END,
       kingdom, phylum, class, "order", family, nullif(genus, '')
FROM (SELECT * FROM src_taxonomy_12s UNION ALL SELECT * FROM src_taxonomy_coi);
