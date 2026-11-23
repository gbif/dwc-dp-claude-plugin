"""The packages GBIF's DwC-DP analyser is run on, to record its reports in tests/fixtures/.

    python3 tests/analyser_packages.py <empty folder>

builds them, one subfolder each. A good package is made from the toy survey; every other one
changes one thing in a copy of it. The test AnalyserReports builds the same packages and compares
`check` with the recorded reports.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "dwc-dp", "scripts", "dwcdp.py")
TOY = os.path.join(ROOT, "tests", "fixtures", "toy-survey")

EML_WITHOUT_CREATOR = """<?xml version="1.0" encoding="UTF-8"?>
<eml:eml xmlns:eml="https://eml.ecoinformatics.org/eml-2.2.0" packageId="toy" system="toy">
  <dataset>
    <title>Toy survey</title>
    <contact><individualName><surName>Berg</surName></individualName></contact>
  </dataset>
</eml:eml>
"""


def edit_descriptor(change):
    def apply(folder):
        path = os.path.join(folder, "datapackage.json")
        with open(path, encoding="utf-8") as fh:
            dp = json.load(fh)
        change(dp, {r["name"]: r for r in dp["resources"]})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(dp, fh, indent=2)
    return apply


def edit_file(name, old, new, count=1):
    def apply(folder):
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert old in text, (name, old)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, count))
    return apply


def write_file(name, text):
    def apply(folder):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    return apply


def drop_column(table, field):
    """Remove a field from both the descriptor and the CSV, so that only the rule under test is broken."""
    def apply(folder):
        edit_descriptor(lambda dp, res: res[table]["schema"].update(
            fields=[f for f in res[table]["schema"]["fields"] if f["name"] != field]))(folder)
        path = os.path.join(folder, f"{table}.csv")
        import csv
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        i = rows[0].index(field)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, lineterminator="\n").writerows([r[:i] + r[i + 1:] for r in rows])
    return apply


def add_column(table, descriptor, value):
    def apply(folder):
        edit_descriptor(lambda dp, res: res[table]["schema"]["fields"].append(descriptor))(folder)
        path = os.path.join(folder, f"{table}.csv")
        import csv
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        rows = [rows[0] + [descriptor["name"]]] + [r + [value] for r in rows[1:]]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, lineterminator="\n").writerows(rows)
    return apply


def field(table, name):
    return lambda res: next(f for f in res[table]["schema"]["fields"] if f["name"] == name)


PACKAGES = {
    "good": [],
    "duplicate-field": [edit_descriptor(lambda dp, res: res["occurrence"]["schema"]["fields"].append(dict(res["occurrence"]["schema"]["fields"][0])))],
    "changed-title": [edit_descriptor(lambda dp, res: res["occurrence"]["schema"]["fields"][0].update(title="Record"))],
    "wrong-type": [edit_descriptor(lambda dp, res: field("event", "eventDate")(res).update(type="integer"))],
    "no-name": [edit_descriptor(lambda dp, res: dp.pop("name"))],
    "broken-link": [edit_file("occurrence.csv", "A2:2025-05-01,", "nowhere,")],
    "missing-required-field": [drop_column("event", "eventCategory")],
    "custom-field": [add_column("event", {"name": "weather", "title": "Weather", "description": "The weather during the visit.",
                                          "type": "string", "format": "default", "dcterms:isVersionOf": "http://example.org/terms/weather"}, "sunny")],
    "undeclared-relationship": [edit_descriptor(lambda dp, res: res["occurrence"]["schema"].pop("foreignKeys"))],
    "changed-predicate": [edit_descriptor(lambda dp, res: res["occurrence"]["schema"]["foreignKeys"][0].update(predicate="during"))],
    "unknown-type": [edit_descriptor(lambda dp, res: field("event", "recordedBy")(res).update(type="text"))],
    "missing-title": [edit_descriptor(lambda dp, res: field("event", "recordedBy")(res).pop("title"))],
    "no-resource-profile": [edit_descriptor(lambda dp, res: res["event"].pop("profile"))],
    "path-outside": [edit_descriptor(lambda dp, res: res["event"].update(path="../event.csv"))],
    "duplicate-key": [edit_file("occurrence.csv", "A2:2025-05-01:Turdus merula", "A1:2025-05-01:Turdus merula")],
    "empty-key": [edit_file("occurrence.csv", "A2:2025-05-01:Turdus merula,", ",")],
    "eml-without-creator": [write_file("eml.xml", EML_WITHOUT_CREATOR)],
    "eml-not-xml": [write_file("eml.xml", "<eml:eml><dataset><title>Toy survey</title></dataset>")],
}


def run(*args, cwd):
    r = subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stdout + r.stderr)


def build(folder):
    """Build every package under folder (which must be empty or new). Returns their names."""
    os.makedirs(folder, exist_ok=True)
    work = os.path.join(folder, ".work")
    os.makedirs(work)
    for f in ("sites.csv", "counts.csv", "mapping.sql"):
        shutil.copy(os.path.join(TOY, f), work)
    with open(os.path.join(work, "id.sql"), "w") as fh:
        fh.write("UPDATE event SET recordedByID = 'https://orcid.org/0000-0002-1825-0097';")
    run("init", "event", "occurrence", cwd=work)
    run("load", "sites.csv", "--sep", ";", cwd=work)
    run("load", "counts.csv", cwd=work)
    run("run", "mapping.sql", cwd=work)
    run("run", "id.sql", cwd=work)
    good = os.path.join(folder, "good")
    run("package", good, "--name", "toy", cwd=work)
    shutil.rmtree(work)
    for name, changes in PACKAGES.items():
        if name == "good":
            continue
        target = os.path.join(folder, name)
        shutil.copytree(good, target)
        for change in changes:
            change(target)
    return list(PACKAGES)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if os.path.exists(sys.argv[1]) and os.listdir(sys.argv[1]):
        sys.exit(f"{sys.argv[1]} is not empty.")
    for name in build(sys.argv[1]):
        print(os.path.join(sys.argv[1], name))
