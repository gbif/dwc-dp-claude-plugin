# Recipe: eDNA and metabarcoding

## When it applies

DNA was extracted from samples (water, soil, sediment, air, bulk insects) and sequenced, and the
result is a table of reads per sequence (ASV or OTU) and sample, with a taxonomy assigned to each
sequence. The files usually are:

- a sample sheet: site, date, coordinates, volume, sample type, controls;
- per marker, an OTU/ASV table (sequences as rows, samples as columns, read counts), a taxonomy
  table and the sequences;
- the methods: primers, PCR, sequencing, pipeline, reference databases.

Sediment cores and other dated material (sedaDNA) also need `paleo.md`.

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
     schema example), its storage and disposition. Who extracted it and when is a
     `material-agent-role` row (role `extracted by`, date in `agentRoleDate`).
3. **Protocols:** one per marker, with:
   - `assayType` `metabarcoding` (a schema example), and `target_gene` as GBIF's concept name;
   - the primers with their names and reference;
   - the reference database in `otu_db`, and the volume extracted in `samp_vol_we_dna_ext`.
4. **Sequences:** every ASV of both markers.
5. **Analyses:**
   - turn each OTU table into one row per ASV and sample, with the marker as a column. Either load
     it long (`load 12S_otu_table.tsv --as otu_12s --unpivot asv --into sample,reads`), or use
     `UNPIVOT` in SQL. A table with hundreds of columns is easier the first way;
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

## Names from a sequence matching tool

Names often come from matching each sequence against a reference database: BLAST, vsearch, or
GBIF's sequence ID tool (https://www.gbif.org/tools/sequence-id). Its export has, per sequence,
`identity`, `matchType`, `scientificName` (for COI often a BOLD BIN such as `BOLD:AAA0001`) and
`classification`. A match is not an identification yet: how far each one can be trusted is the data
holder's rule.

**The match types** of GBIF's sequence ID tool depend on identity alone (gbif/gbif-web,
`vsearch.ctrl.js` and `vsearchParser.js`):

| `matchType` | When |
|---|---|
| `BLAST_EXACT_MATCH` | identity of 99 % or more |
| `BLAST_AMBIGUOUS_MATCH` | an exact match, with another name also an exact match within 1 % of it |
| `BLAST_CLOSE_MATCH` | 97 % or more |
| `BLAST_WEAK_MATCH` | below 97 %, however low |
| `BLAST_NO_MATCH` | nothing found |

Query coverage isn't part of it, so a short alignment can still be an exact match. Check the
alignment length when the export has it.

**Agree on a rule** for the most specific rank each match supports, before mapping. Offer this one,
from a test run, for them to confirm or change:
- exact: the most specific name;
- ambiguous and close: the genus at most;
- weak: the order at most from 85 % identity, and no name below that;
- no match: no name.

A sequence without a name is still a sequence, and can be published. Write the rule in a
`protocol` row linked from each identification (`identificationProtocol_fk`). In
`identificationRemarks`, give each identification its match type and identity.

**Read the classification by rank, never by position.** The export joins names with `_` and leaves
out ranks with no name. So `Animalia_Mollusca_Gastropoda_Planorbidae_Gyraulus` has no order, and
read by position its family lands in `order`. Get each name's rank from a ranked source:
- the reference database's own taxonomy;
- a ranked list the data holder confirms;
- with their agreement, a name lookup such as GBIF's species match, which sends the names only.

Endings help to spot mistakes, but they don't settle a rank: family names end in `-idae` in
zoology and `-aceae` in botany.

**The BIN.** A BOLD BIN is an identifier of a sequence cluster, not a Linnaean name. The example
keeps it in `verbatimIdentification` with the classification, and names the identification with
the most specific Linnaean name the rule allows. Some data holders want the BIN as
`scientificName`. How GBIF interprets a BIN there is not settled here: say so, and let them choose.

**Contaminants and the unexpected.** Weak matches name taxa that weren't sampled, such as sponges
or red algae in an insect trap. Human, dog and pig DNA came up with a 16S marker in a test run.
Show them the names outside what their method can catch, and ask what is published. An agreed exclusion is
written down in `mapping.sql`; a name is never dropped silently.

The worked example is `tests/fixtures/edna-sequence-id/`. It is made up, in the layout of the tool's
export, with one of each match type, a weak sponge match, a human sequence and a classification
without an order:
- the export loads with `load --unwrap`, since every one of its lines is wrapped in quotes;
- `ranks.csv` gives each name's rank;
- the agreed rule names five of the seven sequences: the sponge (79 % identity) and the sequence
  with no match get none, and the human sequence stays out;
- the mollusc is named at class, because its classification has no order.

## Occurrences for GBIF

The analyses and identifications carry the result, and the package is valid without occurrences.
But GBIF is at an early stage of indexing DwC-DP, and currently indexes records through the
`occurrence` table (the maintainers, 2026-11-25). So at the end, ask whether to derive occurrences
from the analyses (SKILL.md, Stage 7). The conceptual model says inferred occurrences should come
with quality control or confidence measures, which is what the filters are for.

**What one occurrence is.** Usually one name at one sampling event. With several markers, ask:
- one occurrence supported by both markers, as in the example;
- or one per marker.

Reads from two markers are two libraries, so a summed read count says little. Leave out the
quantity, or keep one per marker.

**Filters.** Agree on each, and put them at the top of the occurrence part of `mapping.sql` as lists
they can read:
- **names that are contamination,** such as *Homo sapiens* or Hominidae, and pets or livestock.
  Match the list against every rank of the identification, so that `Hominidae` also catches a
  sequence named only to family;
- **controls and blanks.** A blank often shares its event with a real sample, as in the example, so
  filter by the material, not the event;
- **weak names,** such as those below a rank or a match type (see "Names from a sequence matching
  tool");
- **too few reads,** if they use a threshold.

Show how many occurrences each filter removes, and which names. Everything left out stays in
`identification`, `nucleotide-sequence` and `nucleotide-analysis`: only the occurrences leave it out.

**The name.** GBIF takes an occurrence's name from the one identification pointing to it
(`occurrence_fk`) with `isAcceptedIdentification` true (gbif/pipelines, `OccurrenceEnrichment`). The
identifications of the sequences can't do this: one sequence is found at many events. So give each
occurrence an identification based on it:
- copy the name and its ranks;
- set `identificationType` to `nucleotideAnalysis`;
- in `identificationRemarks`, say which sequences it came from.

The example ends with this part: `tests/fixtures/edna-two-markers/`.
- Its filters leave out human DNA and the field blank. The blank shares its event with sample S1,
  so without the filter its Clupeidae reads would become an occurrence at Kalø Vig.
- The result is seven occurrences, each with one accepted identification. The human sequence and
  its identification are still in the package.

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
    `institutionCode`, `collectionCode` and `catalogNumber` when it is in a collection). Ask
    whether the samples or extracts are in a collection, such as a biobank or a lab's freezer
    collection, and whose (SKILL.md, Stage 3). Sample sheets rarely say;
  - material that no longer exists is `used up`.

  A kept sample is what lets someone re-analyse it later, so it is worth recording even when the
  reads are the main result.
- **When derived material was made** (filtering, extraction): no event is needed. Who and when go
  in a `material-agent-role` row, as the example does for the extracts; see "Recording a
  derivation" in `specimens.md`. The filters have no date or person in the example, so they only
  have the link.
- **The reference database** goes in `otu_db`, with its name and version (for example
  `BOLD 2025-05`). This is the maintainers' decision (2026-11-23), and the MDT does the same.
  - The schema's description of `otu_db` is the MIxS one, for clustering genomes into
    "species-level" OTUs.
  - `ref_db` (for ORF annotation) is not used for it.
- **`target_gene`.**
  - GBIF reads it with its `target_gene` vocabulary (`dwcdp.py vocab target_gene`), for example
    `SSU_rRNA_12S_mitochondrial` and `COI`.
  - Their own name ("12S rRNA") may be recognised only loosely. Convert to the concept name only
    with their agreement, as the example does.
- **When one protocol is two.** The same primers on two sequencing runs, or with two pipelines or
  reference databases, can be two protocols. Ask. Check which samples went into each run with
  `sql` before naming the protocols: a run can hold samples from several years or sites, so name a
  protocol after its run, not after the samples it seems to belong to.
- **Occurrences.** The package is valid without them, but GBIF currently needs them to index the
  data. See "Occurrences for GBIF" below.
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
- **A read table, sequences and taxonomy that cover different OTUs.** Filtering steps (length,
  chimeras, LULU) remove OTUs from one file and not the others, and a taxonomy can cover only some
  OTUs. Count what is in each and in all of them (SKILL.md, Stage 1), and ask which set is
  published. `processedTotalReadCount` follows that choice.
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
- GBIF's sequence ID tool: gbif/gbif-web (Apache-2.0) at `25b61d55c0`,
  `packages/graphql-api/src/api-utils/vsearch.ctrl.js` (the thresholds 99 and 97) and
  `src/helpers/vsearch/vsearchParser.js` (`getMatchType`, `getMatch`).
- Family-group name endings: the International Code of Zoological Nomenclature, Article 29.2
  (`-idae`), and the International Code of Nomenclature for algae, fungi, and plants, Article 18.1
  (`-aceae`).
- Primers in the example: MiFish-U (https://doi.org/10.1098/rsos.150088) and mlCOIintF/jgHCO2198
  (https://doi.org/10.1186/1742-9994-10-34). The sequences, reads and database versions are made
  up.
