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
        # The toy keeps its names on the occurrence, so the only finding is the advice to use
        # identification instead.
        out = self.ok("validate")
        self.assertIn("The identification table is preferred", out)
        self.assertNotIn("Must be fixed", out)
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
        self.assertNotIn("Must be fixed", self.ok("check", "out"))

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


class Suggest(Base):
    def test_columns_with_and_without_fields(self):
        with open(os.path.join(self.dir, "samples.csv"), "w") as fh:
            fh.write("sample,habitat,depth,pH,colour,note\nS1,seagrass,1.5,8.1,green,calm\nS2,sand,2.0,8.0,brown,\n")
        self.ok("load", "samples.csv")
        rows = {line.split()[0]: line for line in self.ok("suggest", "samples", "--table", "event").splitlines()[2:] if line.strip() and not line.startswith(("A match", "\n"))}
        self.assertIn("event.habitat", rows["habitat"])
        self.assertIn("maybe event.", rows["depth"])
        self.assertIn("DepthInMeters", rows["depth"])
        self.assertIn("looks like a measurement for event-assertion", rows["pH"])
        self.assertIn("a fact for event-assertion", rows["colour"])
        self.assertIn("maybe event.fieldNotes", rows["note"])


class SurveyRecipe(Base):
    """The worked example of references/recipes/survey.md validates, packages and checks."""

    TABLES = ["event", "survey", "survey-target", "survey-target-descriptor", "survey-survey-target", "occurrence", "event-assertion",
              "identification"]

    def test_point_counts(self):
        src = os.path.join(FIXTURES, "survey-point-counts")
        for f in ("sites.csv", "visits.csv", "counts.csv", "mapping.sql"):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", *self.TABLES)
        for f in ("sites", "visits", "counts"):
            self.ok("load", f"{f}.csv")
        self.ok("run", "mapping.sql")
        out = self.ok("validate")
        self.assertIn("No problems found", out)
        q = lambda sql: self.ok("sql", sql).split("\n")[2].split()
        self.assertEqual(q("SELECT count(*) FROM survey"), ["3"])
        self.assertEqual(q("SELECT count(*) FROM event WHERE parentEvent_fk = 'PC2025'"), ["3"])
        self.assertEqual(q("SELECT count(*) FROM occurrence WHERE occurrenceStatus = 'notDetected'"), ["2"])
        self.assertEqual(q("SELECT string_agg(i.scientificName, '|' ORDER BY i.scientificName) FROM occurrence o "
                           "JOIN identification i ON i.occurrence_fk = o.occurrence_pk WHERE o.surveyTarget_fk IS NULL"),
                         ["Larus", "canus|Lepus", "europaeus"])
        self.ok("package", "out", "--name", "point-counts-2025")
        self.assertIn("No problems found", self.ok("check", "out"))
        with open(os.path.join(self.dir, "out", "survey.csv")) as fh:
            self.assertIn(",10,minutes", fh.read())
        self.assertEqual(q("SELECT assertionValue || ' ' || assertionUnit FROM event_assertion WHERE assertionID = 'V2:wind force'"), ["3", "Beaufort"])


class SurveyMaterialRecipe(Base):
    """The second worked example of references/recipes/survey.md: trap catches kept as material."""

    def test_malaise_catches(self):
        src = os.path.join(FIXTURES, "survey-malaise-bulk")
        files = ["catches.csv", "vouchers.csv", "extracts.csv", "marker.csv", "otu_table.tsv", "taxonomy.tsv"]
        for f in files + ["mapping.sql"]:
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "survey", "occurrence", "material", "identification",
                "molecular-protocol", "nucleotide-sequence", "nucleotide-analysis", "agent", "material-agent-role")
        for f in files:
            self.ok("load", f)
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        q = lambda sql: self.ok("sql", sql).split("\n")[2].strip()
        self.assertEqual(q("SELECT isPartOfMaterialEntity_fk FROM material WHERE materialEntity_pk = 'NHMD-INS-7001'"), "C1")
        self.assertEqual(q("SELECT count(*) FROM nucleotide_analysis WHERE materialEntity_fk NOT IN ('C1-X', 'C2-X')"), "0")
        self.assertEqual(q("SELECT samplingEffortValue FROM survey WHERE event_fk = 'C1'"), "14.0")
        self.ok("package", "out", "--name", "malaise-2025")
        self.assertIn("No problems found", self.ok("check", "out"))


class SpecimensRecipe(Base):
    """The worked example of references/recipes/specimens.md validates, packages and checks."""

    def test_beetle_collection(self):
        src = os.path.join(FIXTURES, "specimens-beetles")
        for f in ("specimens.csv", "determinations.csv", "tissues.csv", "mapping.sql"):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "occurrence", "material", "identification", "identification-taxon", "material-assertion",
                "agent", "material-agent-role")
        for f in ("specimens", "determinations", "tissues"):
            self.ok("load", f"{f}.csv")
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        q = lambda sql: self.ok("sql", sql).split("\n")[2].strip()
        self.assertEqual(q("SELECT count(*) FROM event"), "2")
        self.assertEqual(q("SELECT derivedFromMaterialEntity_fk FROM material WHERE materialEntity_pk = 'NHMD-TIS-77'"), "NHMD-COL-1002")
        self.assertEqual(q("SELECT scientificName FROM identification WHERE materialEntity_fk = 'NHMD-COL-1002' AND isAcceptedIdentification"), "Carabus problematicus")
        self.assertEqual(q("SELECT scientificName || '/' || taxonFormula FROM identification WHERE verbatimIdentification = 'Amara aff. aenea'"), "Amara/A aff.")
        self.assertEqual(q("SELECT t.scientificName FROM identification_taxon t JOIN identification i ON i.identification_pk = t.identification_fk WHERE i.verbatimIdentification = 'Pterostichus cf. niger'"), "Pterostichus niger")
        self.assertEqual(q("SELECT count(*) FROM identification WHERE scientificName IN ('Pterostichus niger', 'Amara aenea')"), "0")
        self.assertEqual(q("SELECT count(*) FROM (SELECT materialEntity_fk FROM identification WHERE isAcceptedIdentification GROUP BY 1 HAVING count(*) > 1)"), "0")
        self.assertEqual(q("SELECT count(*) FROM material_assertion WHERE assertionType = 'elytron length'"), "3")
        self.assertEqual(q("SELECT agentRole || ' ' || agentRoleDate FROM material_agent_role WHERE materialEntity_fk = 'NHMD-TIS-77'"), "sampled by 2025-01-15")
        self.assertEqual(q("SELECT count(*) FROM material WHERE materialEntityRemarks IS NOT NULL"), "0")
        self.ok("package", "out", "--name", "beetles-2024")
        self.assertIn("No problems found", self.ok("check", "out"))


class SpecimenPartsRecipe(Base):
    """The second worked example of references/recipes/specimens.md: a specimen kept as pieces."""

    def test_mammal_parts(self):
        src = os.path.join(FIXTURES, "specimens-mammal-parts")
        for f in ("specimens.csv", "parts.csv", "mapping.sql"):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "occurrence", "material", "identification", "agent", "material-agent-role")
        self.ok("load", "specimens.csv")
        self.ok("load", "parts.csv")
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        q = lambda sql: self.ok("sql", sql).split("\n")[2].strip()
        self.assertEqual(q("SELECT count(*) FROM material WHERE isPartOfMaterialEntity_fk = 'NHMD-MAM-501'"), "3")
        self.assertEqual(q("SELECT derivedFromMaterialEntity_fk FROM material WHERE materialEntity_pk = 'NHMD-TIS-901'"), "NHMD-MAM-501")
        self.assertEqual(q("SELECT disposition FROM material WHERE materialEntity_pk = 'NHMD-MAM-501-C'"), "on loan")
        self.assertEqual(q("SELECT count(*) FROM identification"), "2")
        self.assertEqual(q("SELECT agentRoleDate FROM material_agent_role WHERE materialEntity_fk = 'NHMD-TIS-901'"), "2024-10-07")
        self.ok("package", "out", "--name", "mammals-2024")
        self.assertIn("No problems found", self.ok("check", "out"))


class ObservationsRecipe(Base):
    """The worked examples of references/recipes/observations.md validate, package and check."""

    def build(self, fixture, files, tables, name):
        src = os.path.join(FIXTURES, fixture)
        for f in files + ["mapping.sql"]:
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", *tables)
        for f in files:
            self.ok("load", f)
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        self.ok("package", "out", "--name", name)
        self.assertIn("No problems found", self.ok("check", "out"))
        return lambda sql: self.ok("sql", sql).split("\n")[2].strip()

    def test_pollinator_notebook(self):
        q = self.build("observations-pollinators", ["observations.csv", "photos.csv"],
                       ["event", "occurrence", "organism-interaction", "agent", "media", "media-agent-role", "occurrence-media",
                        "identification"],
                       "pollinators-2025")
        self.assertEqual(q("SELECT count(*) FROM event"), "3")
        self.assertEqual(q("SELECT s.scientificName || ' > ' || r.scientificName FROM organism_interaction i "
                           "JOIN identification s ON s.occurrence_fk = i.subjectOccurrence_fk "
                           "JOIN identification r ON r.occurrence_fk = i.relatedOccurrence_fk WHERE i.subjectOccurrence_fk = 'O2'"),
                         "Bombus lapidarius > Knautia arvensis")
        self.assertEqual(q("SELECT count(*) FROM organism_interaction i JOIN occurrence s ON s.occurrence_pk = i.subjectOccurrence_fk "
                           "JOIN occurrence r ON r.occurrence_pk = i.relatedOccurrence_fk WHERE s.event_fk <> r.event_fk OR i.event_fk <> s.event_fk"), "0")

    def test_camera_traps_from_camtrap_dp(self):
        shutil.copy(os.path.join(FIXTURES, "observations-camtrap", "datapackage.json"), self.dir)
        q = self.build("observations-camtrap", ["deployments.csv", "media.csv", "observations.csv"],
                       ["event", "event-assertion", "agent", "event-agent-role", "occurrence", "occurrence-assertion", "media",
                        "event-media", "identification"],
                       "camtrap-example")
        # event-level animal observations only: the media-level ones would count the same animals again
        self.assertEqual(q("SELECT count(*) FROM occurrence"), "29")
        self.assertEqual(q("SELECT count(*) FROM occurrence o JOIN src_observations s ON s.observationID = o.occurrence_pk "
                           "WHERE s.observationLevel <> 'event' OR s.observationType <> 'animal'"), "0")
        self.assertEqual(q("SELECT count(*) FROM event WHERE eventType = 'Sensor'"), "4")
        # no image of a person, and only images of published sequences
        self.assertEqual(q("SELECT count(*) FROM media m JOIN src_media s ON s.mediaID = m.media_pk WHERE s.filePublic <> 'true'"), "0")
        self.assertEqual(q("SELECT count(*) FROM event_media em LEFT JOIN occurrence o ON o.event_fk = em.event_fk WHERE o.occurrence_pk IS NULL"), "0")
        self.assertEqual(q("SELECT taxonID FROM identification WHERE scientificName = 'Vulpes vulpes'"),
                         "https://www.checklistbank.org/dataset/COL2023/taxon/5BSG3")
        self.assertEqual(q("SELECT identifiedBy FROM identification i JOIN occurrence_assertion a ON a.occurrence_fk = i.occurrence_fk "
                           "WHERE a.assertionValue = 'machine' LIMIT 1"), "Western Europe species model Version 1")
        self.assertEqual(q("SELECT count(*) FROM event_agent_role WHERE agentRole = 'recorded by'"), "4")

class EdnaRecipe(Base):
    """The worked example of references/recipes/edna.md validates, packages and checks."""

    def test_two_markers_on_the_same_samples(self):
        src = os.path.join(FIXTURES, "edna-two-markers")
        for f in os.listdir(src):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "material", "molecular-protocol", "nucleotide-sequence", "nucleotide-analysis", "identification",
                "event-assertion", "material-assertion", "agent", "material-agent-role")
        for f in ("samples.csv", "filters.csv", "extracts.csv", "markers.csv"):
            self.ok("load", f)
        for f, name in (("12S_otu_table.tsv", "otu_12s"), ("12S_taxonomy.tsv", "taxonomy_12s"),
                        ("COI_otu_table.tsv", "otu_coi"), ("COI_taxonomy.tsv", "taxonomy_coi")):
            self.ok("load", f, "--as", name)
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        q = lambda sql: self.ok("sql", sql).split("\n")[2].strip()
        self.assertEqual(q("SELECT string_agg(molecularProtocol_fk || '=' || processedTotalReadCount, '|' ORDER BY molecularProtocol_fk) "
                           "FROM (SELECT DISTINCT molecularProtocol_fk, processedTotalReadCount FROM nucleotide_analysis WHERE materialEntity_fk = 'S1-X')"),
                         "12S=6000|COI=15012")
        self.assertEqual(q("SELECT count(*) FROM nucleotide_analysis WHERE readCount = 0"), "0")
        self.assertEqual(q("SELECT x.derivedFromMaterialEntity_fk || '<' || f.derivedFromMaterialEntity_fk FROM material x "
                           "JOIN material f ON f.materialEntity_pk = x.derivedFromMaterialEntity_fk WHERE x.materialEntity_pk = 'S1-X'"), "S1-F<S1")
        self.assertEqual(q("SELECT count(*) FROM nucleotide_analysis a JOIN material m ON m.materialEntity_pk = a.materialEntity_fk "
                           "WHERE m.materialEntityCategory IS DISTINCT FROM 'DNA extract'"), "0")
        self.assertEqual(q("SELECT target_gene FROM molecular_protocol WHERE molecularProtocol_pk = '12S'"), "SSU_rRNA_12S_mitochondrial")
        self.assertEqual(q("SELECT assertionValue FROM event_assertion WHERE assertionID = 'Kalø Vig 2025-08-12:water temperature'"), "16.2")
        self.assertEqual(q("SELECT count(*) FROM event_assertion"), "4")
        self.assertEqual(q("SELECT assertionUnit FROM material_assertion WHERE materialEntity_fk = 'S1-X'"), "ng/µl")
        self.assertEqual(q("SELECT count(*) FROM material_agent_role WHERE agentRole = 'extracted by' AND agentRoleDate = '2025-08-20'"), "3")
        self.assertEqual(q("SELECT scientificName || '/' || taxonRank FROM identification WHERE nucleotideSequence_fk = '12S_a3'"), "Clupeidae/family")
        self.ok("package", "out", "--name", "edna-two-markers-2025")
        self.assertIn("No problems found", self.ok("check", "out"))


class DarwinCoreArchive(Base):
    def test_zipped_archive_is_staged_with_term_names(self):
        import zipfile
        src = os.path.join(FIXTURES, "dwca-occurrence")
        with zipfile.ZipFile(os.path.join(self.dir, "archive.zip"), "w") as z:
            for f in os.listdir(src):
                z.write(os.path.join(src, f), f)
        out = self.ok("load-dwca", "archive.zip")
        self.assertIn("2 rows as src_dwca_occurrence", out)
        self.assertIn("1 row as src_dwca_measurementorfact", out)
        self.assertIn("eml.xml", out)
        rows = self.ok("sql", "SELECT occurrenceID, individualCount, basisOfRecord FROM src_dwca_occurrence ORDER BY 1")
        self.assertIn("o1            3                HumanObservation", rows)
        header_rows = self.ok("sql", "SELECT count(*) AS n FROM src_dwca_occurrence WHERE id = 'occurrenceID'")
        self.assertEqual(header_rows.split()[-1], "0")
        self.assertEqual(sorted(f for f in os.listdir(self.dir) if not f.startswith("dwcdp.duckdb")), ["archive.zip"])

    def test_unzipped_folder_works_too(self):
        out = self.ok("load-dwca", os.path.join(FIXTURES, "dwca-occurrence"))
        self.assertIn("coreid, measurementType, measurementValue, measurementUnit", out)


class PaleoRecipe(Base):
    """The worked example of references/recipes/paleo.md validates, packages and checks."""

    def test_sediment_core(self):
        src = os.path.join(FIXTURES, "edna-sediment-core")
        files = sorted(f for f in os.listdir(src) if f.endswith(".tsv"))
        for f in files + ["mapping.sql"]:
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "material", "material-assertion", "bibliographic-resource", "protocol",
                "protocol-reference", "chronometric-age", "geological-context", "material-geological-context",
                "molecular-protocol", "molecular-protocol-reference", "nucleotide-sequence", "nucleotide-analysis",
                "identification")
        for f in files:
            self.ok("load", f)
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        self.ok("package", "out", "--name", "lama-sedadna")
        self.assertIn("No problems found", self.ok("check", "out"))
        q = lambda sql: self.ok("sql", sql).split("\n")[2].strip()
        # the slice depth from the trnL IDs agrees with the depth in the ITS1 IDs of run APMG-17
        self.assertEqual(q("SELECT count(*) FROM src_fungi_samples s JOIN material m ON m.materialEntityID = s.materialSampleID "
                           "JOIN material_assertion a ON a.materialEntity_fk = m.derivedFromMaterialEntity_fk "
                           "WHERE s.sequencingRun = 'APMG-17' AND s.id NOT LIKE '%Lama_' || a.assertionValue || '_%'"), "0")
        self.assertEqual(q("SELECT assertionValue FROM material_assertion WHERE materialEntity_fk = 'PG1341:1820-1821'"), "1820-1821")
        self.assertEqual(q("SELECT string_agg(left(g.geologicalContext_fk, 1) || c.earliestChronometricAge, ',' ORDER BY CAST(c.earliestChronometricAge AS INT)) "
                           "FROM chronometric_age c JOIN material_geological_context g ON g.materialEntity_fk = c.materialDated_fk"),
                         "H3023,H9740,P14142,P23002")
        self.assertEqual(q("SELECT count(*) FROM chronometric_age c JOIN material m ON m.materialEntity_pk = c.materialDated_fk "
                           "WHERE c.event_fk <> m.collectionEvent_fk"), "0")
        self.assertEqual(q("SELECT count(DISTINCT molecularProtocol_fk) FROM nucleotide_analysis WHERE materialEntity_fk = 'ELS110'"), "2")
        self.assertEqual(q("SELECT count(*) FROM nucleotide_analysis WHERE readCount > processedTotalReadCount"), "0")


    def test_fossils_without_dna(self):
        src = os.path.join(FIXTURES, "specimens-fossils")
        for f in ("specimens.csv", "dates.csv", "rocks.csv", "mapping.sql"):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "occurrence", "material", "identification", "geological-context",
                "material-geological-context", "protocol", "geological-material", "chronometric-age")
        for f in ("specimens.csv", "dates.csv", "rocks.csv"):
            self.ok("load", f)
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        self.ok("package", "out", "--name", "fossils")
        self.assertIn("No problems found", self.ok("check", "out"))
        q = lambda sql: self.ok("sql", sql).split("\n")[2].strip()
        self.assertEqual(q("SELECT string_agg(materialEntity_fk, ',' ORDER BY materialEntity_fk) FROM material_geological_context"),
                         "FOS-3,FOS-4,ROCK-1")
        self.assertEqual(q("SELECT earliestAgeOrLowestStage FROM geological_context"), "Maastrichtian")
        self.assertEqual(q("SELECT count(*) FROM chronometric_age WHERE event_fk = 'EXC-2019-3' "
                           "AND CAST(earliestChronometricAge AS INT) > CAST(latestChronometricAge AS INT)"), "2")
        self.assertEqual(q("SELECT coalesce(materialDated_fk, '-') || '/' || coalesce(materialDatedRelationship, '-') "
                           "FROM chronometric_age WHERE chronometricAge_pk = 'AAR-102'"), "-/same layer")
        self.assertEqual(q("SELECT geologicalMaterialNames FROM geological_material"), "chalk | calcite | quartz")


class TrackingRecipe(Base):
    """The worked example of references/recipes/tracking.md validates, packages and checks."""

    def test_argos_whales_from_movebank(self):
        src = os.path.join(FIXTURES, "tracking-argos")
        for f in ("locations.csv", "reference-data.csv", "mapping.sql"):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "organism", "identification", "organism-assertion", "occurrence", "agent",
                "event-agent-role", "event-assertion")
        self.ok("load", "locations.csv")
        self.ok("load", "reference-data.csv", "--as", "reference")
        self.ok("run", "mapping.sql")
        out = self.ok("validate")
        self.assertNotIn("Must be fixed", out)
        self.assertIn("'Calf → Juvenile'", out)
        self.ok("package", "out", "--name", "humpback-tracking")
        self.assertNotIn("Must be fixed", self.ok("check", "out"))
        q = lambda sql: self.ok("sql", sql).split("\n")[2].strip()
        # raw fixes only, without the outliers; every occurrence belongs to its whale
        self.assertEqual(q("SELECT count(*) FROM occurrence"), "48")
        self.assertEqual(q("SELECT count(*) FROM occurrence WHERE organism_fk IS NULL"), "0")
        self.assertEqual(q("SELECT count(*) FROM event e JOIN src_locations l ON l.\"event-id\" = e.event_pk "
                           "WHERE l.modelled = 'true' OR l.visible = 'false'"), "0")
        self.assertEqual(q("SELECT string_agg(DISTINCT coalesce(CAST(coordinateUncertaintyInMeters AS INT), 0) || '=' || georeferenceRemarks[-1:], ',' "
                           "ORDER BY coalesce(CAST(coordinateUncertaintyInMeters AS INT), 0) || '=' || georeferenceRemarks[-1:]) FROM event WHERE georeferenceRemarks IS NOT NULL"),
                         "0=0,0=A,0=B,1500=1,250=3,500=2")
        self.assertEqual(q("SELECT count(*) FROM identification"), "3")
        self.assertEqual(q("SELECT lifeStage FROM occurrence WHERE organism_fk = '98109' AND lifeStage IS NOT NULL"), "Calf")
        self.assertEqual(q("SELECT count(*) FROM event e JOIN event d ON d.event_pk = e.parentEvent_fk "
                           "WHERE e.eventDate LIKE '%Z' AND d.eventType <> 'Sensor'"), "0")


    def test_suggest_recognises_movebank_attributes(self):
        src = os.path.join(FIXTURES, "tracking-argos")
        for f in ("locations.csv", "reference-data.csv"):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("load", "locations.csv")
        self.ok("load", "reference-data.csv", "--as", "reference")
        out = self.ok("suggest", "locations")
        rows = {line.split()[0]: line for line in out.splitlines()[2:] if line.strip() and not line.startswith(("This", "A match"))}
        self.assertIn("This looks like a Movebank export (19 of 19 columns", out)
        self.assertIn("Movebank animal ID (MVB000016, individual): organism.organismID", rows["individual-local-identifier"])
        self.assertIn("MVB000209", rows["visible"])
        self.assertIn("no crosswalk entry; an assertion about the location", rows["argos:lat1"])
        rows = {line.split()[0]: line for line in self.ok("suggest", "reference").splitlines()[2:] if line.strip()}
        self.assertIn("event-assertion", rows["duty-cycle"])
        # a table that only shares a few names with Movebank is not taken for one
        with open(os.path.join(self.dir, "notes.csv"), "w") as fh:
            fh.write("site,timestamp,comments,species\nA,2025-01-01 10:00,windy,Apis mellifera\n")
        self.ok("load", "notes.csv")
        self.assertNotIn("Movebank", self.ok("suggest", "notes"))


class MovebankCrosswalk(unittest.TestCase):
    def test_crosswalk_points_to_real_attributes_and_fields(self):
        base = os.path.join(ROOT, "skills", "dwc-dp", "crosswalks")
        with open(os.path.join(base, "movebank-attributes.json")) as fh:
            attrs = {a["id"]: a for a in json.load(fh)["attributes"]}
        with open(os.path.join(base, "movebank.json")) as fh:
            crosswalk = json.load(fh)["attributes"]
        for key, entry in crosswalk.items():
            self.assertIn(key, attrs)
            self.assertEqual(entry["label"], attrs[key]["label"])
            for target in entry["to"]:
                table, _, field = target.partition(".")
                with open(os.path.join(TABLE_SCHEMAS, table + ".json")) as fh:
                    names = [f["name"] for f in json.load(fh)["fields"]]
                if field:
                    self.assertIn(field, names, target)


class AllTables(Base):
    """One row in every DwC-DP table, linked to the rows it can point to, validates, packages and
    checks. This covers the side tables (references/side-tables.md) that no worked example fills."""

    # identification is based on one kind of evidence, and names belong in identification
    SKIP = {("identification", f) for f in ("materialEntity_fk", "media_fk", "nucleotideSequence_fk",
                                            "nucleotideAnalysis_fk", "organism_fk")}
    SKIP |= {("material", "identifiedBy_fk"), ("occurrence", "identifiedBy_fk")}
    VALUES = {("occurrence", "occurrenceStatus"): "'detected'"}

    def mapping(self):
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import dwcdp
        ordered, cycle = dwcdp.fill_order(list(dwcdp.schemas()))
        self.assertEqual(cycle, [])
        lines, links = [f"DELETE FROM {dwcdp.db_name(t)};" for t in reversed(ordered)], 0
        for t in ordered:
            s = dwcdp.schema(t)
            fks = {f: target for f, _, target, _ in dwcdp.keys(s, "foreignKeys")}
            cols, vals = [], []
            for f in s["fields"]:
                n, c = f["name"], f.get("constraints", {})
                if n == s.get("primaryKey"):
                    v = f"'{t}:1'"
                elif n in fks:
                    if fks[n] == t or (t, n) in self.SKIP:
                        continue
                    v, links = f"'{fks[n]}:1'", links + 1
                elif (t, n) in self.VALUES:
                    v = self.VALUES[(t, n)]
                elif not c.get("required"):
                    continue
                elif f["type"] in ("number", "integer"):
                    v = str(c.get("minimum", 1))
                elif f["type"] == "boolean":
                    v = "true"
                else:
                    v = f"'{n}'"
                cols.append(f'"{n}"')
                vals.append(v)
            lines.append(f'INSERT INTO {dwcdp.db_name(t)} ({", ".join(cols)}) VALUES ({", ".join(vals)});')
        return ordered, "\n".join(lines), links

    def test_every_table_validates_packages_and_checks(self):
        tables, sql, links = self.mapping()
        self.assertEqual(len(tables), 81)
        self.assertGreater(links, 150)
        with open(os.path.join(self.dir, "mapping.sql"), "w") as fh:
            fh.write(sql)
        self.ok("init", *tables)
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        self.assertIn("81 tables", self.ok("package", "out", "--name", "all-tables"))
        out = self.ok("check", "out")
        self.assertIn("No problems found", out)
        self.assertEqual(out.count("(1 row)"), 81)
        # a broken link in a side table is found
        with open(os.path.join(self.dir, "break.sql"), "w") as fh:
            fh.write("UPDATE survey_protocol SET protocol_fk = 'nothing';")
        self.ok("run", "break.sql")
        self.assertIn("survey-protocol", self.fails("validate"))

    def test_every_table_is_named_in_the_references(self):
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import dwcdp
        refs = os.path.join(ROOT, "skills", "dwc-dp", "references")
        text = ""
        for folder, _, files in os.walk(refs):
            for f in files:
                with open(os.path.join(folder, f)) as fh:
                    text += fh.read()
        missing = [t for t in dwcdp.schemas() if f"`{t}`" not in text
                   and not any(t == f"{m}{suffix}" for suffix in ("-agent-role", "-identifier", "-reference", "-protocol",
                                                                    "-provenance", "-usage-policy", "-media", "-assertion")
                               for m in dwcdp.schemas())]
        self.assertEqual(missing, [])


class DwcaRecipe(Base):
    """The worked examples of references/recipes/dwca.md validate, package and check."""

    def translate(self, fixture, tables, name):
        src = os.path.join(FIXTURES, fixture)
        shutil.copy(os.path.join(src, "mapping.sql"), self.dir)
        self.ok("load-dwca", src)
        self.ok("init", *tables)
        self.ok("run", "mapping.sql")
        self.assertIn("No problems found", self.ok("validate"))
        self.ok("package", "out", "--name", name, "--eml", os.path.join(src, "eml.xml")) if os.path.exists(os.path.join(src, "eml.xml")) else self.ok("package", "out", "--name", name)
        self.ok("check", "out")
        return lambda sql: self.ok("sql", sql).split("\n")[2].strip()

    def test_occurrence_core(self):
        q = self.translate("dwca-occurrence-core", ["event", "occurrence", "material", "identification", "media",
                                                    "occurrence-media", "material-assertion"], "beetles-djursland")
        self.assertEqual(q("SELECT count(*) FROM event"), "2")
        self.assertEqual(q("SELECT count(*) FROM material"), "2")
        self.assertEqual(q("SELECT family FROM identification WHERE occurrence_fk = 'OBS-77'"), "Carabidae")
        self.assertEqual(q("SELECT organismQuantity || ' ' || organismQuantityType FROM occurrence WHERE occurrence_pk = 'OBS-77'"), "2 individuals")
        self.assertEqual(q("SELECT format FROM media"), "image/jpeg")
        self.assertEqual(q("SELECT count(*) FROM material_assertion"), "2")

    def test_associated_taxa_become_interactions(self):
        q = self.translate("dwca-associated-taxa", ["event", "occurrence", "identification", "organism-interaction"],
                           "fungi-associated-trees")
        self.assertEqual(q("SELECT count(*) FROM organism_interaction"), "5")
        self.assertEqual(q("SELECT s.scientificName || ' ' || i.organismInteractionType || ' ' || r.scientificName "
                           "FROM organism_interaction i JOIN identification s ON s.occurrence_fk = i.subjectOccurrence_fk "
                           "JOIN identification r ON r.occurrence_fk = i.relatedOccurrence_fk WHERE i.subjectOccurrence_fk = 'F-1'"),
                         "Boletus edulis mycorrhizal symbiont of Fagus")
        self.assertEqual(q("SELECT coalesce(organismInteractionType, '(none)') || ' / ' || organismInteractionDescription "
                           "FROM organism_interaction WHERE subjectOccurrence_fk = 'F-5'"), "(none) / gran (Picea)")
        self.assertEqual(q("SELECT count(*) FROM organism_interaction i JOIN occurrence s ON s.occurrence_pk = i.subjectOccurrence_fk "
                           "JOIN occurrence r ON r.occurrence_pk = i.relatedOccurrence_fk WHERE s.event_fk <> r.event_fk OR i.event_fk <> s.event_fk"), "0")

    def test_suggest_flags_columns_that_name_other_organisms(self):
        self.ok("load-dwca", os.path.join(FIXTURES, "dwca-associated-taxa"))
        rows = {line.split()[0]: line for line in self.ok("suggest", "src_dwca_occurrence").splitlines()[2:] if line.strip()}
        self.assertIn("organism-interaction", rows["associatedTaxa"])
        self.assertNotIn("organism-interaction", rows["dynamicProperties"])
        with open(os.path.join(self.dir, "plants.csv"), "w") as fh:
            fh.write("visit,insect,host_plant,temp_C\nV1,Apis mellifera,Knautia arvensis,18.5\n")
        self.ok("load", "plants.csv")
        rows = {line.split()[0]: line for line in self.ok("suggest", "plants").splitlines()[2:] if line.strip()}
        self.assertIn("organism-interaction", rows["host_plant"])
        self.assertNotIn("organism-interaction", rows["visit"])
        self.assertNotIn("organism-interaction", rows["temp_C"])

    def test_event_core(self):
        q = self.translate("dwca-event-core", ["event", "survey", "occurrence", "identification", "event-assertion",
                                               "occurrence-assertion"], "benthos-kalo-2025")
        self.assertEqual(q("SELECT parentEvent_fk FROM event WHERE event_pk = 'KALO-2025-G1'"), "KALO-2025")
        self.assertEqual(q("SELECT minimumDepthInMeters FROM event WHERE event_pk = 'KALO-2025-G1'"), "3.2")
        self.assertEqual(q("SELECT occurrenceStatus FROM occurrence WHERE occurrence_pk = 'G1-2'"), "notDetected")
        self.assertEqual(q("SELECT samplingProtocol FROM survey WHERE event_fk = 'KALO-2025-G2'"), "benthic grab")
        self.assertEqual(q("SELECT occurrence_fk FROM occurrence_assertion"), "G2-1")
        self.assertEqual(q("SELECT count(*) FROM event_assertion WHERE assertionType = 'water depth'"), "0")

    def test_dna_derived_data(self):
        q = self.translate("dwca-dna-derived", ["event", "material", "molecular-protocol", "nucleotide-sequence",
                                                "nucleotide-analysis", "identification"], "ddd-example")
        self.assertEqual(q("SELECT count(*) FROM nucleotide_sequence"), "2")
        self.assertEqual(q("SELECT count(*) FROM molecular_protocol"), "1")
        self.assertEqual(q("SELECT readCount || '/' || processedTotalReadCount FROM nucleotide_analysis WHERE nucleotideAnalysis_pk = 'S1:asv2'"), "1198/16210")
        self.assertEqual(q("SELECT count(DISTINCT materialEntity_fk) FROM nucleotide_analysis WHERE nucleotideSequence_fk = "
                           "(SELECT nucleotideSequence_fk FROM nucleotide_analysis WHERE nucleotideAnalysis_pk = 'S2:asv1')"), "2")

    def test_numbered_terms_get_field_names(self):
        out = self.ok("load-dwca", os.path.join(FIXTURES, "dwca-dna-derived"))
        self.assertIn("target_gene", out)
        self.assertNotIn("0000044", out)

    def test_suggest_matches_archive_columns_by_term(self):
        self.ok("load-dwca", os.path.join(FIXTURES, "dwca-event-core"))
        out = self.ok("suggest", "src_dwca_event")
        rows = {line.split()[0]: line for line in out.splitlines()[2:] if line.strip()}
        self.assertIn("by term: survey.samplingProtocol", rows["samplingProtocol"])
        self.assertIn("record key", rows["id"])
        out = self.ok("suggest", "src_dwca_extendedmeasurementorfact")
        self.assertIn("no DwC-DP field is a version of measurementType", out)


class Summary(Base):
    def test_tables_links_and_example_rows(self):
        src = os.path.join(FIXTURES, "observations-pollinators")
        for f in ("observations.csv", "photos.csv", "mapping.sql"):
            shutil.copy(os.path.join(src, f), self.dir)
        self.ok("init", "event", "occurrence", "organism-interaction", "agent", "media", "media-agent-role",
                "occurrence-media", "identification")
        self.ok("load", "observations.csv")
        self.ok("load", "photos.csv")
        self.ok("run", "mapping.sql")
        out = self.ok("summary", "--rows", "2", "--width", "100")
        self.assertRegex(out, r"organism-interaction\s+\d+\s+An interaction between two")
        self.assertIn("├── occurrence", out)
        self.assertIn("by occurrence (subjectOccurrence_fk", out)
        self.assertIn("identification", out.split("How the tables link")[1].split("├── occurrence")[1])
        self.assertIn("visited flower of", out)
        self.assertNotIn("eventRemarks", out)
        self.assertTrue(all(len(line) <= 100 for line in out.split("rows of each table")[1].split("Ask Claude")[0].splitlines()[1:]))
        self.assertIn("Ask Claude anything", out)

    def test_empty_database_is_refused(self):
        self.ok("init", "event")
        self.assertIn("No DwC-DP table has rows", self.fails("summary"))


class Grscicoll(Base):
    """grscicoll looks codes up in GRSciColl; here against recorded responses on a local server."""

    def setUp(self):
        super().setUp()
        import http.server
        import threading
        import urllib.parse
        src = os.path.join(FIXTURES, "grscicoll")
        self.requests = requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                url = urllib.parse.urlparse(self.path)
                requests.append(url.path + "?" + url.query)
                if url.path == "/lookup":
                    code = urllib.parse.parse_qs(url.query).get("institutionCode", [""])[0]
                    name = "lookup-XMUS.json" if code == "XMUS" else "lookup-none.json"
                else:
                    name = url.path.strip("/").replace("/", "-") + ".json"
                path = os.path.join(src, name)
                if not os.path.exists(path):
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                with open(path, "rb") as fh:
                    self.wfile.write(fh.read())

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.env = os.environ.get("DWCDP_GRSCICOLL_API")
        os.environ["DWCDP_GRSCICOLL_API"] = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        if self.env is None:
            os.environ.pop("DWCDP_GRSCICOLL_API", None)
        else:
            os.environ["DWCDP_GRSCICOLL_API"] = self.env
        super().tearDown()

    def test_codes_give_candidates_with_all_identifiers(self):
        out = self.ok("grscicoll", "--institutionCode", "XMUS", "--collectionCode", "XMUS-F", "--country", "DK")
        self.assertIn("institution: FUZZY DOUBTFUL by CODE_MATCH", out)
        self.assertIn("ROR: https://ror.org/000000000", out)
        self.assertEqual(out.count("ROR:"), 1)
        self.assertIn("WIKIDATA: http://www.wikidata.org/entity/Q0", out)
        self.assertIn("GRSciColl page: https://scientific-collections.gbif.org/collection/00000000-0000-0000-0000-000000000002", out)
        self.assertIn("other codes: XM", out)
        self.assertIn("country=DK", self.requests[0])

    def test_distinct_codes_of_a_table_are_looked_up_once(self):
        with open(os.path.join(self.dir, "specimens.csv"), "w") as fh:
            fh.write("catalogNumber,institutionCode,collectionCode\nA1,XMUS,XMUS-F\nA2,XMUS,XMUS-F\nA3,BM,\nA4,,\n")
        self.ok("load", "specimens.csv")
        result = json.loads(self.ok("grscicoll", "specimens", "--json"))
        self.assertEqual([(r["query"], r["rows"]) for r in result],
                         [({"institutionCode": "XMUS", "collectionCode": "XMUS-F"}, 2), ({"institutionCode": "BM"}, 1)])
        self.assertEqual(len([r for r in self.requests if r.startswith("/lookup")]), 2)
        none = result[1]["institution"]
        self.assertIsNone(none["match"])
        self.assertEqual(none["alternatives"][0]["entity"]["code"], "XMUS")
        self.assertEqual(len([r for r in self.requests if r.startswith("/institution/")]), 1)

    def test_unreachable_service_is_reported(self):
        os.environ["DWCDP_GRSCICOLL_API"] = "http://127.0.0.1:9"
        self.assertIn("Could not reach GRSciColl", self.fails("grscicoll", "--institutionCode", "XMUS"))


class Metadata(Base):
    METADATA = {
        "title": "Toy survey",
        "description": "Made up.\n\nSecond paragraph.",
        "license": "CC-BY-4.0",
        "creators": [{"givenName": "Ann", "surName": "Berg", "orcid": "0000-0002-1825-0097"}],
        "contacts": [{"organization": "Natural History Museum of Denmark", "email": "info@example.org"}],
        "keywords": ["birds"],
        "coverage": {"geographicDescription": "Two sites"},
    }

    def write(self, md):
        with open(os.path.join(self.dir, "metadata.json"), "w") as fh:
            json.dump(md, fh)

    def test_eml_and_descriptor_are_written_from_metadata_json(self):
        import xml.etree.ElementTree as ET
        self.toy()
        self.write(self.METADATA)
        out = self.ok("package", "out", "--name", "toy", "--metadata", "metadata.json")
        self.assertIn("Coverage from the events: south 55.68, north 55.7", out)
        with open(os.path.join(self.dir, "out", "datapackage.json")) as fh:
            dp = json.load(fh)
        self.assertEqual(dp["title"], "Toy survey")
        self.assertEqual(dp["licenses"][0]["name"], "CC-BY-4.0")
        self.assertEqual([(c["title"], c["role"]) for c in dp["contributors"]],
                         [("Ann Berg", "author"), ("Natural History Museum of Denmark", "maintainer")])
        self.assertEqual(dp["contributors"][0]["path"], "https://orcid.org/0000-0002-1825-0097")
        ds = ET.parse(os.path.join(self.dir, "out", "eml.xml")).getroot().find("dataset")
        self.assertEqual([e.tag for e in ds],
                         ["title", "creator", "pubDate", "abstract", "keywordSet", "intellectualRights",
                          "licensed", "coverage", "contact"])
        self.assertEqual(len(ds.find("abstract")), 2)
        self.assertEqual(ds.find("coverage/temporalCoverage/rangeOfDates/beginDate/calendarDate").text, "2025-05-01")
        self.assertEqual(ds.find("contact/organizationName").text, "Natural History Museum of Denmark")
        report = self.ok("check", "out", "--json")
        self.assertNotIn("EML_MISSING", report)

    def test_metadata_without_title_or_contact_is_refused(self):
        self.toy()
        md = dict(self.METADATA, title="", contacts=[])
        self.write(md)
        out = self.fails("package", "out", "--metadata", "metadata.json")
        self.assertIn("title is missing", out)
        self.assertIn("contacts needs at least one", out)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "out")))

    def test_geographic_coverage_needs_a_description(self):
        self.toy()
        self.write(dict(self.METADATA, coverage={}))
        out = self.ok("package", "out", "--name", "toy", "--metadata", "metadata.json")
        self.assertIn("EML needs a geographicDescription", out)

    def test_template_is_not_overwritten(self):
        self.ok("metadata-template")
        self.assertIn("exists", self.fails("metadata-template"))


class IdentificationPlacement(Base):
    def test_a_name_repeated_on_an_identified_occurrence_is_reported(self):
        self.toy()
        self.ok("init", "identification")
        with open(os.path.join(self.dir, "ids.sql"), "w") as fh:
            fh.write("INSERT INTO identification (identification_pk, occurrence_fk, scientificName) "
                     "SELECT occurrence_pk || ':id', occurrence_pk, scientificName FROM occurrence;")
        self.ok("run", "ids.sql")
        out = self.ok("validate")
        self.assertIn("3 rows have identification fields (scientificName) and also an identification", out)
        with open(os.path.join(self.dir, "clear.sql"), "w") as fh:
            fh.write("UPDATE occurrence SET scientificName = NULL;")
        self.ok("run", "clear.sql")
        self.assertIn("No problems found", self.ok("validate"))


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
        self.assertEqual({f for f in found if f[0]}, {("FK_UNKNOWN_REFERENCE_RESOURCE", "warning")})

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
                out[name][1].add((rest.split(" ", 1)[0].rstrip(":"), level.lower()))
            elif line.startswith("Type violation:"):
                out[name][1].add(("DATA_TYPE_VIOLATION", "error"))
            elif line.startswith("FK violation:"):
                out[name][1].add(("FOREIGN_KEY_VIOLATION", "error"))
            elif line.startswith("PK violation:"):
                out[name][1].add(("PRIMARY_KEY_VIOLATION", "error"))
            elif line.startswith("Result: "):
                out[name][0] = line == "Result: VALID"
    return {k: (v[0], v[1]) for k, v in out.items()}


# Where check differs from the analyser on purpose (see references/package.md): it doesn't
# validate EML against the XSD, and it reports malformed EML as a warning, because the analyser's
# error doesn't change its verdict.
NOT_COMPARED = {"EML_XSD_VIOLATION", "EML_XSD_UNAVAILABLE"}
LEVEL_DIFFERS = {"INVALID_XML": ("error", "warning")}


class AnalyserReports(Base):
    """check reaches the verdict GBIF's analyser reached on the same packages, with the same
    findings at the same levels (tests/fixtures/analyser-0.0.16, packages from analyser_packages.py)."""

    def test_check_agrees_with_the_recorded_analyser_reports(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import analyser_packages
        reports = analyser_reports()
        self.assertTrue(set(reports) <= set(analyser_packages.PACKAGES), set(reports) - set(analyser_packages.PACKAGES))
        analyser_packages.build(self.dir)
        for name, (valid, expected) in reports.items():
            expected = {(c, LEVEL_DIFFERS.get(c, (None, lvl))[1] if c in LEVEL_DIFFERS else lvl) for c, lvl in expected if c not in NOT_COMPARED}
            r = run("check", name, "--json", cwd=self.dir)
            found = {(i["analyser"], i["level"]) for i in json.loads(r.stdout)["items"] if i["analyser"]}
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
