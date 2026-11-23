Made up for testing: a Darwin Core Archive with an Event core, unzipped.

- `event.txt`: a survey and its two grab samples (`parentEventID`), with sampling protocol and
  sample size.
- `occurrence.txt`: species per sample, with `present` and `absent` (values GBIF's vocabulary has
  deprecated).
- `extendedmeasurementorfact.txt` (OBIS eMoF): water depth and sediment type of the samples, and the
  wet mass of one occurrence (the rows with an `occurrenceID`).

The NERC vocabulary IRIs are given only for water depth, as an example of `measurementTypeID`.
