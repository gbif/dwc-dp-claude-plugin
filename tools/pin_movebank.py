#!/usr/bin/env python3
"""Copy the Movebank Attribute Dictionary from the NERC Vocabulary Server.

    python3 tools/pin_movebank.py

Movebank publishes its attributes as the NVS collection MVB (http://vocab.nerc.ac.uk/collection/MVB).
This writes skills/dwc-dp/crosswalks/movebank-attributes.json: each attribute's id, IRI, label, alternative
labels, the entity it describes (read from its definition) and whether it is deprecated. The definitions
themselves are not copied: the IRI leads to them.
`dwcdp.py suggest` uses it to recognise the columns of a Movebank export. Where each attribute goes in
DwC-DP is the hand-written crosswalks/movebank.json, which this does not change.
"""
import datetime
import json
import os
import re
import urllib.request

URL = "http://vocab.nerc.ac.uk/collection/MVB/current/?_profile=nvs&_mediatype=application/ld+json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "dwc-dp", "crosswalks",
                   "movebank-attributes.json")


def text(v):
    return (v.get("@value") if isinstance(v, dict) else v or "").strip()


def main():
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"Accept": "application/ld+json"}), timeout=120) as r:
        graph = json.load(r)["@graph"]
    attributes = []
    for c in graph:
        if "/collection/MVB/current/MVB" not in c.get("@id", ""):
            continue
        definition = text(c.get("skos:definition"))
        entity = re.search(r"Entity described: ([^;.]+)", definition)
        attributes.append({
            "id": c["@id"].rstrip("/").rsplit("/", 1)[-1],
            "iri": c["@id"],
            "label": text(c.get("skos:prefLabel")),
            "altLabels": [a.strip() for a in text(c.get("skos:altLabel")).split(";") if a.strip()],
            "entity": entity.group(1).strip() if entity else None,
            "deprecated": text(c.get("owl:deprecated")) == "true",
        })
    attributes.sort(key=lambda a: a["id"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"source": "http://vocab.nerc.ac.uk/collection/MVB/current/",
                   "fetched": datetime.date.today().isoformat(),
                   "attributes": attributes}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"Wrote {len(attributes)} attributes to {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
