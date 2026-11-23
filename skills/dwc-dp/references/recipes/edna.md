# Recipe: eDNA and metabarcoding

## When it applies

DNA was extracted from samples (water, soil, sediment, air, bulk insects) and sequenced, and the
result is a table of reads per sequence (ASV or OTU) and sample, with a taxonomy assigned to each
sequence. The files usually are:

- a sample sheet: site, date, coordinates, volume, sample type, controls;
- per marker, an OTU/ASV table (sequences as rows, samples as columns, read counts), a taxonomy
  table and the sequences;
- the methods: primers, PCR, sequencing, pipeline, reference databases.

A study often uses several markers (assays) on the same samples, for example 12S for fish and COI
for invertebrates. DwC-DP holds them all in one package.

## Tables

| Table | What it holds (from the schema) |
|---|---|
| `event` | the sampling: where and when the sample was taken |
| `material` | the sample, and what was made from it and kept: subsamples, filters, extracts, each derived from the one before (`derivedFromMaterialEntity_fk`) |
| `molecular-protocol` | "A protocol used to perform a dwc:NucleotideAnalysis and potentially derive a dwc:NucleotideSequence from a dwc:MaterialEntity": one row per marker, with target gene, primers and the reference database |
| `nucleotide-sequence` | "A digital representation of a nucleotide sequence": one row per ASV/OTU |
| `nucleotide-analysis` | "A link between a dwc:NucleotideSequence and a dwc:Event and a dwc:MaterialEntity from which it was derived, using a specified dwc:Protocol", with the reads. `molecularProtocol_fk` is required |
| `identification` | the taxonomy assigned to each sequence, *based on* the sequence (`nucleotideSequence_fk`) |

`dwcdp.py order` puts them in this order: event, nucleotide-sequence, material,
molecular-protocol, nucleotide-analysis, identification.

## How several markers fit

The protocol is what tells markers apart:

- **One `molecular-protocol` row per marker.** The marker-specific fields all live there:
  - `target_gene`, `target_subfragment`;
  - `pcr_primer_forward` / `pcr_primer_reverse` and their names, `pcr_primer_reference`;
  - `pcr_cond`, `seq_meth`, and the reference database.
- **One `nucleotide-analysis` row per sample, marker and sequence that has reads.** Its required
  `molecularProtocol_fk` names the marker. The same sample has a set of analyses per marker.
- **The sample is shared.** All markers' analyses point to the same `material` (the extract that
  was amplified) and `event`.
- **Sequences belong to one marker,** because they come from that marker's amplicon.

Read counts compare only within one protocol. Each marker is its own library with its own
sequencing depth, so a sample's totals are per marker (see `processedTotalReadCount` below).

`processedTotalReadCount` is the total read count of the sample. It sits in `nucleotide-analysis`,
next to `readCount`, so that the relative read count of a sequence is `readCount /
processedTotalReadCount` on the same row, without joining tables.

## Keys

- **Samples:** their sample codes as `materialEntityID`.
- **Events:** the site and date, or their sampling event code. A sample and its field blank,
  taken on the same visit, share the event.
- **Protocols:** the marker name, or their assay name if they have one (FAIRe's `assay_name`).
- **Sequences:** their ASV/OTU ids. When the ids of different markers can collide (`asv1` in
  both), prefix them with the marker.
- **Analyses:** the sample and the sequence (`S1:12S_a1`), which is unique because a sequence
  belongs to one marker.
- **Identifications:** derived from the sequence (`id:12S_a1`).

## Mapping, step by step

The worked example is `tests/fixtures/edna-two-markers/`: made up, two water samples and a field
blank, each passed through a filter that is kept, and extracted. Each extract was run with 12S
(MiFish primers) and COI (Leray primers). Each marker has its own OTU table and
taxonomy table. Load those with `--as` so their table names start with a letter (`otu_12s`).

1. **Events:** one per site and date. The blank shares S1's.
2. **Material,** from water to extract:
   - **The water sample:** one row per sample and per blank, with `collectionEvent_fk`. Its
     `materialEntityType` is `Environmental sample` (a schema example), and the blank is marked as
     a negative control in `materialEntityRemarks`.
   - **The filter,** derived from the water, with what it is (`materialDescription`), how it is
     kept (`preparations`: Longmire buffer) and its `disposition` (`in collection`, or `used up`
     for the blank's).
   - **The extract,** derived from the filter, with `materialEntityCategory` `DNA extract` (a
     schema example), its storage and disposition. The extraction date goes in its remarks.
3. **Protocols:** one per marker, with:
   - `assayType` `metabarcoding` (a schema example), and `target_gene` as GBIF's concept name;
   - the primers with their names and reference;
   - the reference database in `otu_db`, and the volume extracted in `samp_vol_we_dna_ext`.
4. **Sequences:** every ASV of both markers.
5. **Analyses:**
   - turn each OTU table into one row per ASV and sample (`UNPIVOT`), with the marker as a column;
   - point each to the sample's extract (`materialEntity_fk`); both markers used the same one;
   - keep the rows with reads;
   - set `processedTotalReadCount` to the sum over the sample and marker
     (`sum(...) OVER (PARTITION BY sample, marker)`).
6. **Identifications:** one per ASV, based on its sequence.
   - `scientificName` is the lowest rank the assignment reached, with `taxonRank` and the higher
     ranks.
   - `identificationType` `nucleotideAnalysis`, a schema example.

7. **Measurements:** these have no field (`references/assertions.md`):
   - water temperature and salinity were measured on site, so they are `event-assertion` rows
     about the sampling event;
   - the DNA concentration is a `material-assertion` row about the extract.

`validate` and `check` pass on it. The analyses show the point of the protocol link:

| material | protocol | sequence | readCount | processedTotalReadCount |
|---|---|---|---|---|
| S1-X | 12S | 12S_a1 | 5120 | 6000 |
| S1-X | 12S | 12S_a2 | 880 | 6000 |
| S1-X | COI | COI_a1 | 15012 | 15012 |

## Choices the data holder makes

- **What `processedTotalReadCount` holds.**
  - It is the sample's total read count, repeated on each of the sample's analysis rows, so that
    `readCount / processedTotalReadCount` gives the relative read count without a join. This is
    the maintainers' answer (2026-11-23), and the MDT writes it the same way.
  - With several markers it is the total per sample and marker (confirmed by the maintainers,
    2026-11-23), because each marker is its own library. A total over all markers would make one
    marker's relative read counts depend on how deeply the others were sequenced.
  - Whether the total is before or after removing controls, contaminants or unassigned reads is
    the data holder's to say.
  - The example sums the reads in the processed table; use their own totals when they have them.
- **`rawTotalReadCount`:** the reads before processing, when they have them, also per sample and
  marker.
- **Zeros.** A 0 in an OTU table gets no analysis row in the example. Whether a 0 should be kept
  (and what it means) is theirs to decide.
- **Controls:**
  - field blanks, extraction blanks and PCR blanks: whether they are published, and how they are
    marked;
  - `molecular-protocol.neg_cont_type` (the substance or equipment used) and `pos_cont_type`
    describe them per protocol.
  - The example publishes the blank with its reads and marks it in the remarks, because a blank
    with reads says something about contamination.
- **What to record as material.** The sample always. Then everything they kept, or want to be
  traceable: subsamples, filters, extracts, each derived from the one before. Then:
  - the analyses point to the material that was amplified, usually the extract, and one extract
    can feed several markers;
  - kept material carries its preservation (`preparations`), where it is (`disposition`, and
    `institutionCode`, `collectionCode` and `catalogNumber` when it is in a collection);
  - material that no longer exists is `used up`.

  A kept sample is what lets someone re-analyse it later, so it is worth recording even when the
  reads are the main result.
- **When derived material was made** (filtering, extraction): see the open question in
  `specimens.md` about derivation events. The example keeps the extraction date in the extract's
  remarks.
- **Where the reference database goes.**
  - The schema has `otu_db`, described as the "Reference database (i.e. sequences not generated as
    part of the current study) used to cluster new genomes in "species-level" OTUs", and `ref_db`,
    described as for ORF annotation. Both are MIxS terms written for genomes, not for amplicon
    taxonomy.
  - The MDT puts the taxonomy reference database in `otu_db`, and the example follows it. This is
    an open question for the maintainers.
- **`target_gene`.**
  - GBIF reads it with its `target_gene` vocabulary (`dwcdp.py vocab target_gene`), for example
    `SSU_rRNA_12S_mitochondrial` and `COI`.
  - Their own name ("12S rRNA") may be recognised only loosely. Convert to the concept name only
    with their agreement, as the example does.
- **When one protocol is two.** The same primers on two sequencing runs, or with two pipelines or
  reference databases, can be two protocols. Ask.
- **Occurrences.**
  - Not needed: the analyses and identifications carry the result.
  - If they want occurrences, they are inferred from the analyses. The conceptual model says these
    should come with quality control or confidence measures.
  - The decision for several markers: when both markers detect the same taxon in a sample, write
    one occurrence supported by both, or one per marker.
- **Identifications.** One per sequence, as in the example. Add more when a sequence was assigned
  with more than one database or method, with `isAcceptedIdentification` for the one they stand
  by.

## Pitfalls

- **ASV ids that repeat across markers** (`asv1` in both tables): the sequence key is not unique,
  and `validate` reports a duplicate `nucleotideSequence_pk`. Prefix them with the marker.
- **One total for a sample across markers:** a total summed over all markers makes the relative
  abundances wrong. Partition by sample *and* marker.
- **A sample column in an OTU table with no row in the sample sheet:** the analyses then point to
  material that doesn't exist, and `validate` reports a broken `materialEntity_fk`.
- **Taxonomy with empty ranks** (assigned only to family): take the lowest filled rank as
  `scientificName`, and set `taxonRank` to match.
- **Table names starting with a digit** (`12S_otu_table.tsv` becomes `src_12s_otu_table`): they
  have to be quoted in SQL. Load them with `--as`.

## Sources

- DwC-DP 1.0 table schemas `nucleotide-analysis`, `nucleotide-sequence`, `molecular-protocol`,
  `material`, `identification` and `event` (the vendored copies), including the descriptions
  quoted above.
- Darwin Core conceptual model, https://dwc.tdwg.org/cm/, section 2.6 (NucleotideAnalysis,
  NucleotideSequence and MolecularProtocol).
- GBIF's DNA derived data extension (https://rs.gbif.org/extension/gbif/1.0/dna_derived_data_2024-07-11.xml),
  which has the same MIxS descriptions for `otu_db` and `ref_db`.
- The GBIF Metabarcoding Data Toolkit's DwC-DP output (gbif/metabarcoding-data-toolkit-backend,
  `converters/dwcdp.js`): one protocol per dataset, `processedTotalReadCount` from the sample's
  total, and the reference database in `otu_db`.
- gbif/dwc-dp-examples `edna/obis-edna-expeditions` at `a9994e8f72` (2026-10-21), from before
  1.0, looked at only for its tables (event, event-assertion, material, molecular-protocol,
  nucleotide-analysis, nucleotide-sequence, identification).
- GBIF's `target_gene` vocabulary (the pinned copy).
- Primers in the example: MiFish-U (https://doi.org/10.1098/rsos.150088) and mlCOIintF/jgHCO2198
  (https://doi.org/10.1186/1742-9994-10-34). The sequences, reads and database versions are made
  up.
