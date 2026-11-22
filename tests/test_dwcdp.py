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
        self.ok("package", "out", "--title", "Toy survey")
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


class Check(Base):
    def test_package_from_before_1_0_is_refused_clearly(self):
        out = self.fails("check", os.path.join(FIXTURES, "natural-keys-package"))
        self.assertIn("profile is 'https://raw.githubusercontent.com/gbif/dwc-dp/0.1", out)
        self.assertIn("primaryKey is 'eventID'; the DwC-DP schema defines 'event_pk'", out)

    def test_wrong_type_is_reported(self):
        self.toy()
        self.ok("package", "out")
        path = os.path.join(self.dir, "out", "event.csv")
        with open(path) as fh:
            text = fh.read()
        with open(path, "w") as fh:
            fh.write(text.replace("55.68", "north"))
        out = self.fails("check", "out")
        self.assertIn("1 value of decimalLatitude is not of type number", out)

    def test_malformed_csv_is_reported_not_crashed(self):
        self.toy()
        self.ok("package", "out")
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
