-- A DNA derived data archive (made up, in the shape the MDT writes), translated to DwC-DP.
-- Load first: dwcdp.py load-dwca <this folder>, which stages src_dwca_occurrence and
-- src_dwca_dnaderiveddata. The choices marked "agreed" are the data holder's; see
-- references/recipes/dwca.md and edna.md.

DELETE FROM identification;
DELETE FROM nucleotide_analysis;
DELETE FROM nucleotide_sequence;
DELETE FROM molecular_protocol;
DELETE FROM material;
DELETE FROM event;

-- One event per sampling event (eventID).
INSERT INTO event (event_pk, eventID, eventCategory, eventDate, locality, decimalLatitude, decimalLongitude, geodeticDatum)
SELECT DISTINCT eventID, eventID, 'material collection', eventDate, locality,
       CAST(decimalLatitude AS DOUBLE), CAST(decimalLongitude AS DOUBLE), geodeticDatum
FROM src_dwca_occurrence;

-- basisOfRecord MaterialSample: the sample is material. Agreed: the archive's eventID also names the
-- sample, as in MDT archives, so the material's key is the eventID.
INSERT INTO material (materialEntity_pk, materialEntityID, collectionEvent_fk, materialEntityType)
SELECT DISTINCT eventID, eventID, eventID, 'Environmental sample'
FROM src_dwca_occurrence
WHERE basisOfRecord = 'MaterialSample';

-- The extension repeats the protocol on every row: one molecular protocol per distinct combination.
-- Agreed: there is one, keyed by its target gene.
INSERT INTO molecular_protocol (molecularProtocol_pk, molecularProtocolID, assayType, target_gene,
                                pcr_primer_name_forward, pcr_primer_forward, pcr_primer_name_reverse,
                                pcr_primer_reverse, pcr_primer_reference, otu_db, seq_meth)
SELECT DISTINCT target_gene, target_gene, 'metabarcoding', target_gene, pcr_primer_name_forward, pcr_primer_forward,
       pcr_primer_name_reverse, pcr_primer_reverse, pcr_primer_reference, otu_db, seq_meth
FROM src_dwca_dnaderiveddata;

-- One sequence per distinct DNA_sequence (the GBIF term dna_sequence, matched by meaning to
-- nucleotide-sequence.sequence, a version of dwc:sequence). The archive has no sequence ids, so
-- agreed: the key is the MD5 of the sequence, the same for the same sequence in every sample.
INSERT INTO nucleotide_sequence (nucleotideSequence_pk, nucleotideSequenceID, sequence)
SELECT DISTINCT md5(dna_sequence), md5(dna_sequence), dna_sequence
FROM src_dwca_dnaderiveddata;

-- One analysis per occurrence row: its reads (organismQuantity in "DNA sequence reads") as
-- readCount, and the sample's total (sampleSizeValue, same unit) as processedTotalReadCount.
-- Agreed: the archive's occurrences are not kept as occurrences; the analyses carry the result.
INSERT INTO nucleotide_analysis (nucleotideAnalysis_pk, nucleotideAnalysisID, event_fk, materialEntity_fk,
                                 molecularProtocol_fk, nucleotideSequence_fk, readCount, processedTotalReadCount)
SELECT o.occurrenceID, o.occurrenceID, o.eventID, o.eventID, d.target_gene, md5(d.dna_sequence),
       CASE WHEN o.organismQuantityType = 'DNA sequence reads' THEN CAST(o.organismQuantity AS BIGINT) END,
       CASE WHEN o.sampleSizeUnit = 'DNA sequence reads' THEN CAST(o.sampleSizeValue AS BIGINT) END
FROM src_dwca_occurrence o JOIN src_dwca_dnaderiveddata d ON d.coreid = o.id;

-- One identification per sequence, based on it. The archive repeats the taxonomy on every row of
-- the same sequence; agreed: it is the same assignment, so one is enough.
INSERT INTO identification (identification_pk, identificationID, nucleotideSequence_fk, identificationType,
                            scientificName, taxonRank, kingdom, phylum)
SELECT DISTINCT 'id:' || md5(d.dna_sequence), 'id:' || md5(d.dna_sequence), md5(d.dna_sequence), 'nucleotideAnalysis',
       o.scientificName, o.taxonRank, o.kingdom, o.phylum
FROM src_dwca_occurrence o JOIN src_dwca_dnaderiveddata d ON d.coreid = o.id;
