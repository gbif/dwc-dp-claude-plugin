# Crosswalks

- `movebank-attributes.json`: the Movebank Attribute Dictionary, as published in the NERC
  Vocabulary Server collection MVB (http://vocab.nerc.ac.uk/collection/MVB/current/): each
  attribute's id, IRI, labels, the entity it describes and whether it is deprecated. Written by
  `tools/pin_movebank.py`; don't edit it by hand. The definitions are at each IRI.
- `movebank.json`: where Movebank attributes go in DwC-DP, written by hand from
  `references/recipes/tracking.md`. `dwcdp.py suggest` uses both to recognise a Movebank export.
