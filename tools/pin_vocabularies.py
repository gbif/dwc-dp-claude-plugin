#!/usr/bin/env python3
"""Copy the GBIF vocabularies that DwC-DP fields are interpreted with.

    python3 tools/pin_vocabularies.py

Which DwC term uses which vocabulary is GBIF's own configuration: `vocabularyConfig` in
gbif/pipelines `gbif/ingestion/spark-jobs/pipelines.yaml`, pinned below. For each vocabulary the
latest release is copied. A vocabulary with no release, or whose export is unavailable, is read
from the concepts API instead, which the README records as a draft. The result replaces
skills/dwc-dp/vocabularies/.
"""
import datetime
import json
import os
import urllib.parse
import urllib.request

API = "https://api.gbif.org/v1/vocabularies"
PIPELINES_COMMIT = "ee8d869e42426430c88c5ebaf72b7d82eda69ef8"
PIPELINES_CONFIG = f"https://github.com/gbif/pipelines/blob/{PIPELINES_COMMIT}/gbif/ingestion/spark-jobs/pipelines.yaml"

# vocabularyConfig.vocabulariesNames in that file. The two keys that are not DwC term URIs say
# where GBIF applies them: GeoTime to the geological context terms, and target_gene to the
# target_gene field of DNA derived data.
VOCABULARIES = {
    "http://rs.tdwg.org/dwc/terms/degreeOfEstablishment": "DegreeOfEstablishment",
    "http://rs.tdwg.org/dwc/terms/lifeStage": "LifeStage",
    "http://rs.tdwg.org/dwc/terms/establishmentMeans": "EstablishmentMeans",
    "http://rs.tdwg.org/dwc/terms/pathway": "Pathway",
    "http://rs.tdwg.org/dwc/terms/eventType": "eventType",
    "GeologicalContext": "GeoTime",
    "http://rs.tdwg.org/dwc/terms/typeStatus": "TypeStatus",
    "http://rs.tdwg.org/dwc/terms/sex": "Sex",
    "http://rs.tdwg.org/dwc/terms/occurrenceStatus": "OccurrenceStatus",
    "http://rs.gbif.org/terms/1.0/DNADerivedData": "target_gene",
}

# The terms GBIF applies GeoTime to: GeologicalContextInterpreter in gbif/pipelines.
GEOTIME_SOURCE = f"https://github.com/gbif/pipelines/blob/{PIPELINES_COMMIT}/sdks/core/src/main/java/org/gbif/pipelines/core/interpreters/core/GeologicalContextInterpreter.java"
GEOTIME_TERMS = [f"http://rs.tdwg.org/dwc/terms/{t}" for t in (
    "earliestEonOrLowestEonothem", "latestEonOrHighestEonothem",
    "earliestEraOrLowestErathem", "latestEraOrHighestErathem",
    "earliestPeriodOrLowestSystem", "latestPeriodOrHighestSystem",
    "earliestEpochOrLowestSeries", "latestEpochOrHighestSeries",
    "earliestAgeOrLowestStage", "latestAgeOrHighestStage")]

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "dwc-dp", "vocabularies")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dwc-dp-claude-plugin"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def labels(value):
    """{lang: text} or [{language, value}] → sorted list of texts."""
    if isinstance(value, dict):
        texts = [t for v in value.values() for t in (v if isinstance(v, list) else [v])]
    else:
        texts = [x.get("value") for x in value or [] if isinstance(x, dict)]
    return sorted({t for t in texts if t})


def from_release(name, version):
    data = get(f"{API}/{name}/releases/{version}/export")
    by_key = {c["key"]: c["name"] for c in data["concepts"]}
    return [{
        "name": c["name"],
        "labels": labels(c.get("label")),
        "alternativeLabels": labels(c.get("alternativeLabels")),
        "hiddenLabels": sorted(set(c.get("hiddenLabels") or [])),
        "deprecated": bool(c.get("deprecated")),
        "replacedBy": by_key.get(c.get("replacedByKey")),
    } for c in data["concepts"]]


def paged(url):
    out, offset = [], 0
    while True:
        sep = "&" if "?" in url else "?"
        page = get(f"{url}{sep}limit=1000&offset={offset}")
        out += page["results"]
        if page.get("endOfRecords", True) or not page["results"]:
            return out
        offset += len(page["results"])


def from_concepts(name):
    concepts = paged(f"{API}/{name}/concepts")
    by_key = {c["key"]: c["name"] for c in concepts}
    out = []
    for c in concepts:
        quoted = urllib.parse.quote(c["name"])
        alt = paged(f"{API}/{name}/concepts/{quoted}/alternativeLabels")
        hidden = paged(f"{API}/{name}/concepts/{quoted}/hiddenLabels")
        out.append({
            "name": c["name"],
            "labels": labels(c.get("label")),
            "alternativeLabels": labels(alt),
            "hiddenLabels": sorted({h.get("value") for h in hidden if h.get("value")}),
            "deprecated": bool(c.get("deprecated")),
            "replacedBy": by_key.get(c.get("replacedByKey")),
        })
    return out


def main():
    os.makedirs(ROOT, exist_ok=True)
    today = datetime.date.today().isoformat()
    rows = []
    for term, name in VOCABULARIES.items():
        releases = get(f"{API}/{name}/releases?limit=1")["results"]
        version = releases[0]["version"] if releases else None
        concepts = None
        if version:
            try:
                concepts = from_release(name, version)
                source = f"release {version}"
            except Exception:
                concepts = None
        if concepts is None:
            concepts = from_concepts(name)
            source = f"draft, read from the concepts API on {today}" + (f" (the export of release {version} was unavailable)" if version else " (no release yet)")
        with open(os.path.join(ROOT, f"{name}.json"), "w", encoding="utf-8") as fh:
            json.dump({"vocabulary": name, "source": source, "concepts": concepts}, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        rows.append((term, name, source, len(concepts)))
        print(f"{name}: {len(concepts)} concepts, {source}")
    with open(os.path.join(ROOT, "mapping.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": PIPELINES_CONFIG, "vocabularies": VOCABULARIES,
                   "geoTimeSource": GEOTIME_SOURCE, "geoTimeTerms": GEOTIME_TERMS}, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(f"""# GBIF vocabularies — pinned copies

Copied by `tools/pin_vocabularies.py` on {today} from {API}. Do not edit; rerun the script.

Which term uses which vocabulary is GBIF's configuration ({PIPELINES_CONFIG}, `vocabularyConfig`),
in `mapping.json`. `GeoTime` applies to the ten chronostratigraphic terms listed there under
`geoTimeTerms` ({GEOTIME_SOURCE}), and `target_gene` to the `target_gene` field.

| Term | Vocabulary | Copied from | Concepts |
|---|---|---|---|
""" + "".join(f"| `{t}` | {n} | {s} | {c} |\n" for t, n, s, c in rows))


if __name__ == "__main__":
    main()
