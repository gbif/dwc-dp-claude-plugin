"""Tests for skills/dwc-dp/scripts/dwcdp.py. Run with: python3 -m unittest discover tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "dwc-dp", "scripts", "dwcdp.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
TABLE_SCHEMAS = os.path.join(ROOT, "skills", "dwc-dp", "schemas", "1.0", "table-schemas")


def run(*args, cwd):
    return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd, capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def ok(self, *args):
        r = run(*args, cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def fails(self, *args):
        r = run(*args, cwd=self.dir)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        return r.stdout + r.stderr

    def toy(self):
        for f in ("sites.csv", "counts.csv", "mapping.sql"):
            shutil.copy(os.path.join(FIXTURES, "toy-survey", f), self.dir)
        self.ok("init", "event", "occurrence")
        self.ok("load", "sites.csv", "--sep", ";")
        self.ok("load", "counts.csv")
        self.ok("run", "mapping.sql")


class Schemas(unittest.TestCase):
    def test_every_foreign_key_points_to_a_table_and_field_that_exist(self):
        tables = {}
        for f in os.listdir(TABLE_SCHEMAS):
            with open(os.path.join(TABLE_SCHEMAS, f)) as fh:
                s = json.load(fh)
            tables[s["name"]] = {x["name"] for x in s["fields"]}
        self.assertEqual(len(tables), 81)
        for f in os.listdir(TABLE_SCHEMAS):
            with open(os.path.join(TABLE_SCHEMAS, f)) as fh:
                s = json.load(fh)
            for k in s.get("foreignKeys", []):
                target = k["reference"]["resource"] or s["name"]
                self.assertIn(target, tables, f"{s['name']}.{k['fields']}")
                self.assertIn(k["reference"]["fields"], tables[target], f"{s['name']}.{k['fields']}")


class SchemaCommands(Base):
    def test_describe_shows_keys_and_relations(self):
        out = self.ok("describe", "occurrence")
        self.assertIn("Primary key: occurrence_pk", out)
        self.assertIn("Public identifier: occurrenceID", out)
        self.assertIn("event_fk → event.event_pk", out)

    def test_describe_accepts_underscore_names(self):
        self.assertIn("material-agent-role", self.ok("describe", "material_agent_role"))

    def test_unknown_table_is_refused(self):
        self.assertIn("No DwC-DP table", self.fails("describe", "specimen"))

    def test_find_term_puts_exact_names_first(self):
        first = self.ok("find-term", "eventDate").splitlines()[2]
        self.assertTrue(first.startswith("event.eventDate"), first)


class Database(Base):
    def test_init_creates_every_table(self):
        names = sorted(f[:-5] for f in os.listdir(TABLE_SCHEMAS))
        self.ok("init", *names)
        out = self.ok("status")
        self.assertEqual(out.count("DwC-DP"), 81)

    def test_toy_survey_validates_packages_and_checks(self):
        self.toy()
        self.assertIn("No problems found", self.ok("validate"))
        self.ok("package", "out", "--title", "Toy survey", "--name", "toy-survey")
        with open(os.path.join(self.dir, "out", "datapackage.json")) as fh:
            dp = json.load(fh)
        self.assertEqual(dp["profile"], "https://rs.tdwg.org/dwc-dp/1.0/dwc-dp-profile.json")
        occ = next(r for r in dp["resources"] if r["name"] == "occurrence")
        self.assertEqual(occ["mediatype"], "text/csv")
        self.assertEqual(occ["schema"]["primaryKey"], "occurrence_pk")
        self.assertEqual([k["fields"] for k in occ["schema"]["foreignKeys"]], ["event_fk"])
        with open(os.path.join(TABLE_SCHEMAS, "occurrence.json")) as fh:
            vendored = {f["name"]: f for f in json.load(fh)["fields"]}
        for f in occ["schema"]["fields"]:
            self.assertEqual(f, vendored[f["name"]])
        with open(os.path.join(self.dir, "out", "occurrence.csv")) as fh:
            header = fh.readline().strip().split(",")
        self.assertEqual(header, [f["name"] for f in occ["schema"]["fields"]])
        self.assertIn("No problems found", self.ok("check", "out"))

    def test_package_refuses_a_folder_with_files(self):
        self.toy()
        os.makedirs(os.path.join(self.dir, "out"))
        open(os.path.join(self.dir, "out", "keep.txt"), "w").close()
        self.assertIn("not empty", self.fails("package", "out"))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "out", "keep.txt")))

    def test_broken_foreign_key_is_reported(self):
        self.toy()
        with open(os.path.join(self.dir, "break.sql"), "w") as fh:
            fh.write("UPDATE occurrence SET event_fk = 'nowhere' WHERE occurrence_pk LIKE 'A2%';")
        self.ok("run", "break.sql")
        out = self.fails("validate")
        self.assertIn("1 row has a value in event_fk that matches no event_pk in event", out)
        self.assertIn("'nowhere'", out)
        self.assertIn("Not packaged", self.fails("package", "out"))

    def test_duplicate_primary_key_and_missing_required_field_are_reported(self):
        self.toy()
        with open(os.path.join(self.dir, "break.sql"), "w") as fh:
            fh.write("INSERT INTO event (event_pk, eventCategory) VALUES ('A1:2025-05-01', 'survey');"
                     "INSERT INTO event (event_pk) VALUES ('E9');")
        self.ok("run", "break.sql")
        out = self.fails("validate")
        self.assertIn("1 value of event_pk (the primary key) occurs more than once", out)
        self.assertIn("1 of 4 rows has no eventCategory, which is required", out)

    def test_failed_sql_changes_nothing(self):
        self.toy()
        with open(os.path.join(self.dir, "bad.sql"), "w") as fh:
            fh.write("DELETE FROM occurrence; SELECT * FROM no_such_table;")
        self.assertIn("nothing was changed", self.fails("run", "bad.sql"))
        self.assertIn("3", self.ok("sql", "SELECT count(*) FROM occurrence"))


class DarwinCoreArchive(Base):
    def test_zipped_archive_is_staged_with_term_names(self):
        import zipfile
        src = os.path.join(FIXTURES, "dwca-occurrence")
        with zipfile.ZipFile(os.path.join(self.dir, "archive.zip"), "w") as z:
            for f in os.listdir(src):
                z.write(os.path.join(src, f), f)
        out = self.ok("load-dwca", "archive.zip")
        self.assertIn("2 rows as src_dwca_occurrence", out)
        self.assertIn("1 rows as src_dwca_measurementorfact", out)
        self.assertIn("eml.xml", out)
        rows = self.ok("sql", "SELECT occurrenceID, individualCount, basisOfRecord FROM src_dwca_occurrence ORDER BY 1")
        self.assertIn("o1            3                HumanObservation", rows)
        header_rows = self.ok("sql", "SELECT count(*) AS n FROM src_dwca_occurrence WHERE id = 'occurrenceID'")
        self.assertEqual(header_rows.split()[-1], "0")
        self.assertEqual(sorted(f for f in os.listdir(self.dir) if not f.startswith("dwcdp.duckdb")), ["archive.zip"])

    def test_unzipped_folder_works_too(self):
        out = self.ok("load-dwca", os.path.join(FIXTURES, "dwca-occurrence"))
        self.assertIn("coreid, measurementType, measurementValue, measurementUnit", out)


class Vocabularies(Base):
    def test_values_outside_gbif_vocabularies_are_warned_about(self):
        self.toy()
        with open(os.path.join(self.dir, "vocab.sql"), "w") as fh:
            fh.write("UPDATE occurrence SET occurrenceStatus = 'seen' WHERE scientificName = 'Erithacus rubecula';"
                     "UPDATE occurrence SET occurrenceStatus = 'Present' WHERE occurrence_pk LIKE 'A2%';"
                     "UPDATE occurrence SET sex = 'female' WHERE occurrence_pk LIKE 'A1%Turdus%';")
        self.ok("run", "vocab.sql")
        out = self.ok("validate")
        self.assertIn("1 value of occurrenceStatus is not in GBIF's OccurrenceStatus vocabulary", out)
        self.assertIn("'seen'", out)
        self.assertIn("deprecated in GBIF's OccurrenceStatus vocabulary", out)
        self.assertIn("'Present → Detected'", out)
        self.assertNotIn("of sex", out)

    def test_vocab_lists_concepts_of_a_field(self):
        out = self.ok("vocab", "occurrence.occurrenceStatus")
        self.assertIn("NotDetected", out)
        self.assertIn("Present (deprecated, use Detected)", out)


class AlignedWithAnalyser(Base):
    """check reports what GBIF's DwC-DP analyser (gbif/dwc-dp-analyser 0.0.16) reports, at its
    default severity, with its violation type as `analyser`."""

    def package(self, change=None, files=None):
        self.toy()
        with open(os.path.join(self.dir, "id.sql"), "w") as fh:
            fh.write("UPDATE event SET recordedByID = 'https://orcid.org/0000-0002-1825-0097';")
        self.ok("run", "id.sql")
        self.ok("package", "out", "--name", "toy", "--overwrite")
        path = os.path.join(self.dir, "out", "datapackage.json")
        with open(path) as fh:
            dp = json.load(fh)
        if change:
            change(dp, {r["name"]: r for r in dp["resources"]})
            with open(path, "w") as fh:
                json.dump(dp, fh)
        for name, text in (files or {}).items():
            with open(os.path.join(self.dir, "out", name), "w") as fh:
                fh.write(text)
        r = run("check", "out", "--json", cwd=self.dir)
        report = json.loads(r.stdout)
        return r.returncode, {(i["analyser"], i["level"]) for i in report["items"]}, report

    def test_a_fresh_package_has_only_the_expected_weak_reference_warning(self):
        code, found, _ = self.package()
        self.assertEqual(code, 0)
        self.assertEqual(found, {("FK_UNKNOWN_REFERENCE_RESOURCE", "warning")})

    def test_duplicate_field_is_an_error(self):
        def change(dp, res):
            res["occurrence"]["schema"]["fields"].append(dict(res["occurrence"]["schema"]["fields"][0]))
        code, found, _ = self.package(change)
        self.assertEqual(code, 1)
        self.assertIn(("FIELD_DUPLICATE", "error"), found)

    def test_changed_title_or_description_is_a_warning(self):
        def change(dp, res):
            res["occurrence"]["schema"]["fields"][0]["title"] = "Record"
            res["occurrence"]["schema"]["fields"][1]["description"] = "The visit."
        code, found, report = self.package(change)
        self.assertEqual(code, 0)
        mismatch = [i for i in report["items"] if i["analyser"] == "FIELD_DEFINITION_MISMATCH"]
        self.assertEqual(sorted(i["message"].split(" a ")[1].split(" ")[0] for i in mismatch), ["description", "title"])

    def test_changed_type_is_a_warning_and_values_are_cast_to_the_declared_type(self):
        def change(dp, res):
            f = next(f for f in res["event"]["schema"]["fields"] if f["name"] == "eventDate")
            f["type"] = "integer"
        code, found, _ = self.package(change)
        self.assertIn(("FIELD_TYPE_MISMATCH", "warning"), found)
        self.assertIn(("DATA_TYPE_VIOLATION", "error"), found)
        self.assertEqual(code, 1)

    def test_missing_title_is_an_error(self):
        def change(dp, res):
            del res["event"]["schema"]["fields"][2]["title"]
        code, found, _ = self.package(change)
        self.assertIn(("FIELD_DEFINITION_MISSING", "error"), found)
        self.assertIn(("JSON_SCHEMA_VIOLATION", "warning"), found)
        self.assertEqual(code, 1)

    def test_custom_field_is_information_only(self):
        def change(dp, res):
            res["event"]["schema"]["fields"].append({"name": "weather", "title": "Weather", "description": "x", "type": "string", "dcterms:isVersionOf": "http://example.org/weather"})
        code, found, _ = self.package(change)
        self.assertIn(("UNKNOWN_FIELD", "info"), found)

    def test_undeclared_and_unknown_relationships_are_warnings(self):
        def change(dp, res):
            res["occurrence"]["schema"]["foreignKeys"][0]["predicate"] = "during"
        code, found, _ = self.package(change)
        self.assertEqual(code, 0)
        self.assertIn(("FOREIGN_KEY_MISSING", "warning"), found)
        self.assertIn(("FOREIGN_KEY_NOT_IN_CANONICAL_SCHEMA", "warning"), found)

    def test_missing_required_field_is_an_error(self):
        def change(dp, res):
            res["event"]["schema"]["fields"] = [f for f in res["event"]["schema"]["fields"] if f["name"] != "eventCategory"]
        code, found, report = self.package(change)
        self.assertIn(("REQUIRED_FIELD_MISSING", "error"), found)
        self.assertFalse(any("the required field eventCategory is missing" in i["message"] for i in report["items"]))

    def test_path_outside_the_package_is_an_error(self):
        def change(dp, res):
            res["event"]["path"] = "../event.csv"
        code, found, _ = self.package(change)
        self.assertIn(("PATH_NOT_FOUND", "error"), found)
        self.assertEqual(code, 1)

    def test_missing_package_name_is_a_warning(self):
        def change(dp, res):
            del dp["name"]
        code, found, _ = self.package(change)
        self.assertEqual(code, 0)
        self.assertIn(("MISSING_NAME", "warning"), found)

    def test_eml_problems_are_warnings(self):
        code, found, _ = self.package(files={"eml.xml": "<eml><dataset><title>T</title></dataset></eml>"})
        self.assertEqual(code, 0)
        self.assertIn(("EML_MISSING_CREATOR", "warning"), found)
        code, found, _ = self.package(files={"eml.xml": "<eml><dataset>"})
        self.assertIn(("INVALID_XML", "warning"), found)

    def test_unrecognised_profile_skips_the_analysers_schema_checks(self):
        def change(dp, res):
            dp["profile"] = "https://example.org/profile.json"
            res["event"]["schema"]["fields"][2]["title"] = "Other"
        code, found, _ = self.package(change)
        self.assertIn(("UNRECOGNIZED_PROFILE_VERSION", "error"), found)
        self.assertIn((None, "warning"), found)
        self.assertNotIn(("FIELD_DEFINITION_MISMATCH", "warning"), found)


def analyser_reports():
    """{package: (valid, {(code, level)})} from the recorded reports of GBIF's analyser."""
    out, name = {}, None
    with open(os.path.join(FIXTURES, "analyser-0.0.16", "reports.txt")) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("== "):
                name = line[3:]
                out[name] = [None, set()]
            elif line.startswith("[") and "] " in line:
                level, rest = line[1:].split("] ", 1)
                out[name][1].add((rest.split(" ", 1)[0], level.lower()))
            elif line.startswith("Type violation:"):
                out[name][1].add(("DATA_TYPE_VIOLATION", "error"))
            elif line.startswith("FK violation:"):
                out[name][1].add(("FOREIGN_KEY_VIOLATION", "error"))
            elif line.startswith("PK violation:"):
                out[name][1].add(("PRIMARY_KEY_VIOLATION", "error"))
            elif line.startswith("Result: "):
                out[name][0] = line == "Result: VALID"
    return {k: (v[0], v[1]) for k, v in out.items()}


def change_duplicate_field(dp, res):
    res["occurrence"]["schema"]["fields"].append(dict(res["occurrence"]["schema"]["fields"][0]))


def change_title(dp, res):
    res["occurrence"]["schema"]["fields"][0]["title"] = "Record"


def change_type(dp, res):
    next(f for f in res["event"]["schema"]["fields"] if f["name"] == "eventDate")["type"] = "integer"


def remove_name(dp, res):
    dp.pop("name")


def break_link(folder):
    path = os.path.join(folder, "occurrence.csv")
    with open(path) as fh:
        text = fh.read()
    with open(path, "w") as fh:
        fh.write(text.replace("A2:2025-05-01,", "nowhere,", 1))


ANALYSED = {
    "good": (None, None),
    "duplicate-field": (change_duplicate_field, None),
    "changed-title": (change_title, None),
    "wrong-type": (change_type, None),
    "no-name": (remove_name, None),
    "broken-link": (None, break_link),
}


class AnalyserReports(Base):
    """check reaches the verdict GBIF's analyser reached on the same packages, with the same
    findings at the same levels (tests/fixtures/analyser-0.0.16)."""

    def test_check_agrees_with_the_recorded_analyser_reports(self):
        reports = analyser_reports()
        self.assertEqual(set(reports), set(ANALYSED))
        self.toy()
        with open(os.path.join(self.dir, "id.sql"), "w") as fh:
            fh.write("UPDATE event SET recordedByID = 'https://orcid.org/0000-0002-1825-0097';")
        self.ok("run", "id.sql")
        self.ok("package", "good", "--name", "toy")
        for name, (change, change_files) in ANALYSED.items():
            folder = os.path.join(self.dir, name)
            if name != "good":
                shutil.copytree(os.path.join(self.dir, "good"), folder)
            if change:
                path = os.path.join(folder, "datapackage.json")
                with open(path) as fh:
                    dp = json.load(fh)
                change(dp, {r["name"]: r for r in dp["resources"]})
                with open(path, "w") as fh:
                    json.dump(dp, fh)
            if change_files:
                change_files(folder)
            r = run("check", name, "--json", cwd=self.dir)
            found = {(i["analyser"], i["level"]) for i in json.loads(r.stdout)["items"] if i["analyser"]}
            valid, expected = reports[name]
            with self.subTest(package=name):
                self.assertEqual(r.returncode == 0, valid)
                self.assertEqual(found, expected)


class Check(Base):
    def test_package_from_before_1_0_is_refused_clearly(self):
        out = self.fails("check", os.path.join(FIXTURES, "natural-keys-package"))
        self.assertIn("profile is 'https://raw.githubusercontent.com/gbif/dwc-dp/0.1", out)
        self.assertIn("primaryKey is 'eventID'; the DwC-DP schema defines 'event_pk'", out)

    def test_wrong_type_is_reported(self):
        self.toy()
        self.ok("package", "out", "--name", "toy")
        path = os.path.join(self.dir, "out", "event.csv")
        with open(path) as fh:
            text = fh.read()
        with open(path, "w") as fh:
            fh.write(text.replace("55.68", "north"))
        out = self.fails("check", "out")
        self.assertIn("1 value of decimalLatitude is not of type number", out)

    def test_malformed_csv_is_reported_not_crashed(self):
        self.toy()
        self.ok("package", "out", "--name", "toy")
        path = os.path.join(self.dir, "out", "event.csv")
        with open(path) as fh:
            text = fh.read()
        with open(path, "w") as fh:
            fh.write(text.replace("55.68", "55,68"))
        out = self.fails("check", "out")
        self.assertIn("could not be read as CSV", out)
        self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()
