A small slice of published data: sedimentary ancient DNA (sedaDNA) from the Lake Lama core PG1341
(Siberia, cored 1997), from von Hippel et al. (2022), Quaternary Science Reviews 295, 107758,
https://doi.org/10.1016/j.quascirev.2022.107758. The data are on Dryad,
https://doi.org/10.5061/dryad.05qfttf3x (CC0 1.0).

Cut from the MDT input made from the Dryad files (one row per PCR replicate, ages from the Dryad
`*_samples_ages.xlsx` sheets):

- four depth slices of the core, two Holocene and two Pleistocene: extracts ELS125 (3023 cal yr BP),
  ELS123 (9740), ELS121 (14142) and ELS110 (23002);
- `fungi_*.tsv`: ITS1, 17 PCR replicates of those extracts in two sequencing runs, and the 6 OTUs
  with most reads in them; `plants_*.tsv`: trnL, 12 PCR replicates and 6 OTUs;
- `*_samples.tsv` has `total_reads`, each replicate's reads over all OTUs of the full table, since
  the cut keeps only six;
- `markers.tsv`: the two assays, from the MDT input's default values.

The sample IDs hold the depths. The trnL IDs name the core section and its depth, and the slice's
depth within the section (`PG1341-11_1783-1883cm_37-38cm`): the slice is at 1783 + 37 = 1820 cm.
The ITS1 IDs of run APMG-17 give the same depth directly (`Lama_1820-1821`).

Left out: extract ELS122, whose age is 11317 cal yr BP in the ITS1 sheet and 13209 in the trnL
sheet.
