# Fixtures

- `toy-survey/`: made up for these tests, a point count at two sites.
- `natural-keys-package/`: made up, a package in the shape used before DwC-DP 1.0 (`eventID` as
  the key, a 0.1 profile), for testing that `check` refuses it clearly.
- `dwca-occurrence/`: made up, a Darwin Core Archive (unzipped) with an occurrence core, a
  measurement extension and a default value in `meta.xml`.
- `survey-point-counts/`: made up, bird point counts (two sites, three visits, zeros, a gull and
  a hare outside the target) with a methods text; the worked example of
  `skills/dwc-dp/references/recipes/survey.md`.
- `analyser-0.0.16/`: reports of GBIF's DwC-DP analyser on the packages of
  `tests/analyser_packages.py`.
- `specimens-beetles/`: made up, a beetle collection export (specimens, a lot, determination history
  with a "cf.", a tissue sample); the worked example of `skills/dwc-dp/references/recipes/specimens.md`.
- `observations-pollinators/`: made up, a field notebook of flowers and their visitors with photos; a
  worked example of `skills/dwc-dp/references/recipes/observations.md`.
- `observations-camtrap/`: made up, the three tables of a Camtrap DP package (deployments, media,
  observations, including a blank and a person); the other worked example of `observations.md`.
- `edna-two-markers/`: made up, two water samples and a field blank run with 12S and COI, an OTU
  table and taxonomy per marker; the worked example of `skills/dwc-dp/references/recipes/edna.md`.
