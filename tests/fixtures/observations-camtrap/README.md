The example dataset of Camtrap DP 1.0.2, unchanged:
https://github.com/tdwg/camtrap-dp/tree/1.0.2/example. A sample of "MICA - Muskrat and coypu camera
trap observations in Belgium, the Netherlands and Germany" (Desmet P, Neukermans A, Van der beeck D,
Cartuyvels E 2022, INBO). Data CC0 1.0; the images it links to are CC BY 4.0
(`datapackage.json` `licenses`).

- `deployments.csv`: four camera deployments.
- `media.csv`: 423 images, 60 of them not public (those showing people).
- `observations.csv`: 549 observations at two levels. 36 classify a whole sequence
  (`observationLevel` event), 513 a single image (`observationLevel` media). Most are by a person,
  22 by a machine model.
- `datapackage.json`: the package descriptor, with the taxa (`taxonomic`) and the licences.
