Made up for testing: an eDNA study with two markers on the same samples.

- `samples.csv`: two water samples and a field blank (a negative control), one litre each.
- `filters.csv`: the filter each sample was passed through, kept in Longmire buffer (the blank's
  is used up).
- `extracts.csv`: the DNA extract made from each filter, with when and by whom, and whether it is
  kept.
- `markers.csv`: the two assays, 12S (MiFish primers) and COI (Leray primers), with the reference
  database each was assigned with.
- `12S_otu_table.tsv`, `COI_otu_table.tsv`: reads per ASV and sample, one table per marker. The
  columns are the sample codes; the extract amplified is the sample's in `extracts.csv`.
- `12S_taxonomy.tsv`, `COI_taxonomy.tsv`: each ASV's sequence and assigned taxonomy. One 12S ASV
  is assigned only to family.

Sequences, read counts and reference database versions are invented.
