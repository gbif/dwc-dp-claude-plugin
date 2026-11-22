# GBIF vocabularies — pinned copies

Copied by `tools/pin_vocabularies.py` on 2026-11-22 from https://api.gbif.org/v1/vocabularies. Do not edit; rerun the script.

Which term uses which vocabulary is GBIF's configuration (https://github.com/gbif/pipelines/blob/ee8d869e42426430c88c5ebaf72b7d82eda69ef8/gbif/ingestion/spark-jobs/pipelines.yaml, `vocabularyConfig`),
in `mapping.json`. `GeoTime` applies to the ten chronostratigraphic terms listed there under
`geoTimeTerms` (https://github.com/gbif/pipelines/blob/ee8d869e42426430c88c5ebaf72b7d82eda69ef8/sdks/core/src/main/java/org/gbif/pipelines/core/interpreters/core/GeologicalContextInterpreter.java), and `target_gene` to the `target_gene` field.

| Term | Vocabulary | Copied from | Concepts |
|---|---|---|---|
| `http://rs.tdwg.org/dwc/terms/degreeOfEstablishment` | DegreeOfEstablishment | release 1.0.3 | 15 |
| `http://rs.tdwg.org/dwc/terms/lifeStage` | LifeStage | release 1.0.4 | 39 |
| `http://rs.tdwg.org/dwc/terms/establishmentMeans` | EstablishmentMeans | release 1.0.3 | 6 |
| `http://rs.tdwg.org/dwc/terms/pathway` | Pathway | release 1.0.3 | 53 |
| `http://rs.tdwg.org/dwc/terms/eventType` | eventType | draft, read from the concepts API on 2026-11-22 (no release yet) | 12 |
| `GeologicalContext` | GeoTime | draft, read from the concepts API on 2026-11-22 (the export of release 1.0.0 was unavailable) | 176 |
| `http://rs.tdwg.org/dwc/terms/typeStatus` | TypeStatus | release 0.0.1 | 51 |
| `http://rs.tdwg.org/dwc/terms/sex` | Sex | release 1.0.0 | 5 |
| `http://rs.tdwg.org/dwc/terms/occurrenceStatus` | OccurrenceStatus | release 1.0.0 | 4 |
| `http://rs.gbif.org/terms/1.0/DNADerivedData` | target_gene | release 1.0.0 | 86 |
