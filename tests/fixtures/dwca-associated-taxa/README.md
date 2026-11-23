Made up for testing: a Darwin Core Archive of fungus finds, unzipped, in the shape of a fungal
records database export (no eml.xml).

- `occurrence.txt`: six finds on two days. `associatedTaxa` names the tree each fungus grew with,
  as "vernacular (genus)"; `dynamicProperties` holds the substrate. Neither says what kind of
  association it was.

The interactions are implicit: each `associatedTaxa` value is a second organism at the same find.
`mapping.sql` makes it an occurrence with its own identification, and an `organism-interaction`
between the two. The type comes from the substrate by a rule the data holder gave (made up here,
see the mapping's header); finds on other substrates get an untyped interaction.
