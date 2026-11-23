# Interactions: when a record names a second organism

Data often hold interactions without calling them that. A fungus "on *Fagus*", a beetle "ex
*Quercus*", a bee with its flower, a parasite with its host, a stomach with its prey: each of these
is a second organism, seen together with the one recorded. DwC-DP has tables for that, and an
assertion is not one of them. An assertion is a measurement or fact about one thing (see
`assertions.md`). A second organism is a thing of its own, with its own name.

## Spot them in Stage 1

Look at the values, not only the column names. A column is an interaction candidate when its
values name another organism, by scientific or common name:

- **Darwin Core terms:** `associatedTaxa`, `associatedOccurrences`, `associatedOrganisms`, and a
  ResourceRelationship extension in an archive. No DwC-DP field is a version of the first two.
  `suggest` flags these terms;
- **column names** such as host, host plant, food plant, prey, predator, parasite, pollinator,
  visited, partner or associated species. `suggest` flags these words too;
- **free text** that names an organism: "on *Betula*", "ex *Quercus robur*", "reared from",
  "host: …", in remarks, habitat, substrate or label text;
- **a second name column in the same row**, such as `plant_species` next to `insect_species`.

`suggest` can't see an organism named only in the values, so read a few values of every column
without a field before calling it an assertion.

## Which table

Read each table's definition and notes with `describe` before proposing it. In short:

| What the data say | Table |
|---|---|
| two organisms seen interacting during an event: one on, in, eating, visiting or parasitising the other | `organism-interaction`, between two `occurrence` rows |
| a permanent relationship between two organisms that are tracked over time: mother of, sibling of | `organism-relationship`, between two `organism` rows |
| a relationship between other kinds of record, such as a specimen and the photo of its label | `resource-relationship` |

The notes of `organism-interaction` say it "supports only primary observed interactions, not
habitual or derived taxon-level interactions". So ask: was the partner seen with this organism, at
this find? A tree named at the find is an observed interaction. A host taken from the literature
for the species ("*Boletus edulis* is mycorrhizal with *Fagus*") is not, and stays out, or goes in
remarks, as the data holder decides.

## How to build one

For each record that names a partner:

1. **The partner is an occurrence** in the same event as the subject, with `occurrenceStatus`
   `detected`. It usually has no identifier of its own: leave `occurrenceID` empty and generate
   `occurrence_pk` from the subject's key (`F-1:associated`), and say so.
2. **The partner's name goes in `identification`**, based on that occurrence, as for any other
   name. The value as written goes in `verbatimIdentification`. Split a value such as
   `bøg (Fagus)` into `vernacularName` and `scientificName` only when the pattern holds for every
   value and the data holder agrees.
3. **The interaction** has these fields:
   - `subjectOccurrence_fk`: the actor;
   - `relatedOccurrence_fk`: the acted-upon. The schema's notes say to "typify the action rather
     than the state", with the actor as subject: the bee visited the flower, the fungus is a
     parasite of the tree;
   - `event_fk`: the event of both;
   - `organismInteractionType`: a phrase read from subject to related, such as `visited flower of`
     or `parasite of`. The schema recommends a controlled vocabulary, and gives `visited flower of`,
     `pollinated by`, `parasitoid of`, `mated with` and `was attached to` as examples;
   - `organismInteractionDescription`: the value as written (`bøg (Fagus)`), so nothing is lost;
   - `subjectOrganismPart` and `relatedOrganismPart`: the parts involved, such as `flower` or
     `leaf`, when stated.
4. **More than one partner** in a value (`Fagus | Quercus`) means one partner occurrence and one
   interaction per partner. The notes say that "pairwise interactions must be used".
5. **A partner recorded elsewhere,** for example a host specimen in another collection, goes in
   `relatedOccurrenceID` (or `externalRelatedOccurrenceID` with `externalRelatedOccurrenceSource`),
   instead of a new occurrence. Do this only when the data give its identifier.

Fill the tables in this order: `event`, `occurrence`, `identification`, `organism-interaction`.

## The type is theirs

The data rarely say what kind of interaction it was. Never infer the type from the names ("a
fungus with a tree is mycorrhizal"). Ask. Three outcomes are all fine:

- **They state it,** or a column does (`interaction = "feeding on"`).
- **They give a rule** from another column, such as the substrate: soil means mycorrhizal, dead
  wood saprophyte, bark of living trees parasite. Show them every distinct value of that column
  with its count and the type the rule gives. Values the rule doesn't cover clearly stay untyped,
  unless they say otherwise.
- **It stays empty.** The interaction is still recorded, with the verbatim description.

## Questions for the data holder

- Was the partner seen at the find, or is it known for the species from elsewhere?
- Which of the two acts on the other?
- What kind of interaction is it, or which column tells?
- Can a value name more than one partner? What separates them?

## Worked examples

- `tests/fixtures/observations-pollinators/`: explicit interactions, where a visitor's row names the
  flower's row (`observations.md`).
- `tests/fixtures/dwca-associated-taxa/`: implicit ones in a Darwin Core Archive.
  `associatedTaxa` names the tree each fungus grew with, and the substrate gives the type by the
  data holder's rule. Finds on other substrates get an untyped interaction.

## Sources

- DwC-DP 1.0 table schemas `organism-interaction`, `organism-relationship`, `resource-relationship`
  and `organism` (the vendored copies): definitions, notes and examples.
- Darwin Core conceptual model, https://dwc.tdwg.org/cm/ (non-normative).
