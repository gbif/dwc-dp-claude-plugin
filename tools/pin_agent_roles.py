#!/usr/bin/env python3
"""Copy GBIF's EML agent role vocabulary: the roles of associated parties and project personnel.

    python3 tools/pin_agent_roles.py

The vocabulary is https://rs.gbif.org/vocabulary/gbif/agent_role.xml, read at the commit of
gbif/rs.gbif.org pinned below. That repository states no licence, so only the identifiers, URIs and
English titles are copied, not the descriptions. The result replaces
skills/dwc-dp/eml/agent-roles.json.
"""
import datetime
import json
import os
import urllib.request
import xml.etree.ElementTree as ET

COMMIT = "09b54849788fae2063a28b97274532b15e77022d"
URL = f"https://raw.githubusercontent.com/gbif/rs.gbif.org/{COMMIT}/vocabulary/gbif/agent_role.xml"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "dwc-dp", "eml", "agent-roles.json")
DC = "{http://purl.org/dc/terms/}"
TH = "{http://rs.gbif.org/thesaurus/}"
XML = "{http://www.w3.org/XML/1998/namespace}"


def main():
    with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "dwc-dp-claude-plugin"}), timeout=60) as r:
        root = ET.fromstring(r.read())
    roles = []
    for c in root.iter(f"{TH}concept"):
        title = next((t.get(f"{DC}title") for t in c.iter(f"{TH}term") if t.get(f"{XML}lang") == "en"), None)
        roles.append({"role": c.get(f"{DC}identifier"), "uri": c.get(f"{DC}URI"), "title": title})
    out = {
        "vocabulary": root.get(f"{DC}URI"),
        "title": root.get(f"{DC}title"),
        "source": URL,
        "copied": datetime.date.today().isoformat(),
        "note": "Identifiers, URIs and English titles only: the source repository states no licence.",
        "roles": roles,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"{len(roles)} roles written to {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
