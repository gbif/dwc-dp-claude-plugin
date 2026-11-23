Made up for testing: a Darwin Core Archive of DNA derived data, in the shape the GBIF
Metabarcoding Data Toolkit writes. Unzipped, without metadata.

- `occurrence.txt`: one row per sample and sequence, with the reads as `organismQuantity`
  ("DNA sequence reads") and the sample's total reads as `sampleSizeValue`. One sequence is in
  both samples; one is assigned only to family.
- `dna.txt` (DNA derived data extension): the sequence, target gene, primers, reference database
  and sequencing method of each row.

Sequences, reads and the database version are invented; the primers are the Leray COI primers.
