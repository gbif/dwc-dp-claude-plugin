#!/usr/bin/env python3
"""Build and check Darwin Core Data Packages (DwC-DP) with DuckDB.

The working database (default ./dwcdp.duckdb) holds the data holder's source files as src_*
tables and the DwC-DP tables they are mapped into. Table names use underscores
(material_agent_role for material-agent-role); column names are the DwC-DP field names.

  python3 dwcdp.py tables                      # every DwC-DP table, one line each
  python3 dwcdp.py describe occurrence         # fields, keys and relations of one table
  python3 dwcdp.py find-term depth             # where a term lives
  python3 dwcdp.py vocab occurrence.lifeStage  # the GBIF vocabulary a field is read with
  python3 dwcdp.py order event occurrence agent  # which to fill first
  python3 dwcdp.py init event occurrence       # create DwC-DP tables in the database
  python3 dwcdp.py load samples.csv            # stage a source file as src_samples
  python3 dwcdp.py load-dwca archive.zip       # stage a Darwin Core Archive
  python3 dwcdp.py run mapping.sql             # fill the DwC-DP tables
  python3 dwcdp.py validate                    # check them, in plain words
  python3 dwcdp.py package out/                # write CSVs and datapackage.json
  python3 dwcdp.py check out/                  # check any DwC-DP package on disk

Needs Python 3.8+ and the duckdb package (pip install duckdb).
"""
import argparse
import csv
import datetime
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "1.0"
SCHEMA_DIR = os.path.join(HERE, "..", "schemas", VERSION)
PROFILE_URL = f"https://rs.tdwg.org/dwc-dp/{VERSION}/dwc-dp-profile.json"
SQL_TYPES = {"string": "VARCHAR", "integer": "BIGINT", "number": "DOUBLE", "boolean": "BOOLEAN"}
EXAMPLES_SHOWN = 5


# ---------------------------------------------------------------- schemas

_schemas = None


def schemas():
    """{table name: table schema} for every DwC-DP table, as vendored."""
    global _schemas
    if _schemas is None:
        d = os.path.join(SCHEMA_DIR, "table-schemas")
        _schemas = {}
        for f in sorted(os.listdir(d)):
            if f.endswith(".json"):
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    s = json.load(fh)
                _schemas[s["name"]] = s
        _schemas = dict(sorted(_schemas.items()))
    return _schemas


def schema(name):
    s = schemas().get(dwc_name(name))
    if not s:
        close = [t for t in schemas() if dwc_name(name).split("-")[0] in t][:8]
        sys.exit(f"No DwC-DP table '{name}'." + (f" Did you mean: {', '.join(close)}?" if close else " Run: dwcdp.py tables"))
    return s


def dwc_name(name):
    return name.replace("_", "-")


def db_name(name):
    return name.replace("-", "_")


def field_map(s):
    return {f["name"]: f for f in s["fields"]}


def constraints(f):
    return f.get("constraints") or {}


def as_list(v):
    return v if isinstance(v, list) else [v]


def keys(s, kind):
    """foreignKeys or weakForeignKeys as (field, predicate, target table, target field). An empty
    reference resource means the table itself."""
    out = []
    for k in s.get(kind) or []:
        ref = k.get("reference") or {}
        out.append((as_list(k["fields"])[0], k.get("predicate", ""), ref.get("resource") or s["name"], as_list(ref.get("fields"))[0]))
    return out


def referenced_by(name):
    out = []
    for t, s in schemas().items():
        for field, pred, target, tfield in keys(s, "foreignKeys"):
            if target == name and t != name:
                out.append((t, field, pred))
    return out


def first_sentence(text, limit=160):
    text = " ".join((text or "").split())
    m = re.match(r"(.+?\.)(\s|$)", text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[: limit - 1] + "…"


# ---------------------------------------------------------------- GBIF vocabularies

VOCAB_DIR = os.path.join(HERE, "..", "vocabularies")
_vocab = None


def vocabularies():
    """(mapping, {name: vocabulary}) from the pinned copies in ../vocabularies."""
    global _vocab
    if _vocab is None:
        with open(os.path.join(VOCAB_DIR, "mapping.json"), encoding="utf-8") as fh:
            mapping = json.load(fh)
        vocabs = {}
        for name in set(mapping["vocabularies"].values()):
            with open(os.path.join(VOCAB_DIR, f"{name}.json"), encoding="utf-8") as fh:
                v = json.load(fh)
            lookup = {}
            for c in v["concepts"]:
                for text in c["hiddenLabels"]:
                    lookup.setdefault(text.strip().lower(), (c, "hidden"))
                for text in [c["name"]] + c["labels"] + c["alternativeLabels"]:
                    lookup[text.strip().lower()] = (c, "accepted")
            v["lookup"] = lookup
            vocabs[name] = v
        _vocab = (mapping, vocabs)
    return _vocab


def field_vocabulary(f):
    """The GBIF vocabulary GBIF interprets this field with, or None (see ../vocabularies/README.md)."""
    mapping, _ = vocabularies()
    term = f.get("dcterms:isVersionOf")
    if term in mapping["geoTimeTerms"]:
        return "GeoTime"
    if term in mapping["vocabularies"]:
        return mapping["vocabularies"][term]
    if f.get("name") == "target_gene":
        return mapping["vocabularies"].get("http://rs.gbif.org/terms/1.0/DNADerivedData")
    return None


def check_vocabularies(con, name, table, cols, report):
    _, vocabs = vocabularies()
    for f in schemas()[name]["fields"]:
        vname = field_vocabulary(f)
        if not vname or f["name"] not in cols:
            continue
        v = vocabs[vname]
        values = con.execute(f"SELECT trim(CAST({q(f['name'])} AS VARCHAR)) AS v, count(*) FROM {q(table)} WHERE {q(f['name'])} IS NOT NULL AND trim(CAST({q(f['name'])} AS VARCHAR)) <> '' GROUP BY 1 ORDER BY 2 DESC").fetchall()
        unknown, hidden, deprecated = [], [], []
        for value, n in values:
            hit = v["lookup"].get(value.lower())
            if not hit:
                unknown.append(value)
            elif hit[1] == "hidden":
                hidden.append(f"{value} → {hit[0]['name']}")
            elif hit[0]["deprecated"]:
                deprecated.append(f"{value}" + (f" → {hit[0]['replacedBy']}" if hit[0]["replacedBy"] else ""))
        where = f"GBIF's {vname} vocabulary ({v['source']})"
        names = [c["name"] for c in v["concepts"] if not c["deprecated"]]
        options = f" Its concepts: {', '.join(names)}." if len(names) <= 12 else f" See: dwcdp.py vocab {vname}"
        if unknown:
            report.warning(name, f"{len(unknown)} {'value' if len(unknown) == 1 else 'values'} of {f['name']} {'is' if len(unknown) == 1 else 'are'} not in {where}, so GBIF won't interpret {'it' if len(unknown) == 1 else 'them'}.{options}", unknown, f["name"])
        if hidden:
            report.warning(name, f"{len(hidden)} {'value' if len(hidden) == 1 else 'values'} of {f['name']} {'is' if len(hidden) == 1 else 'are'} read by GBIF as a concept of {where}; writing the concept's name says the same thing plainly.", hidden, f["name"])
        if deprecated:
            report.warning(name, f"{len(deprecated)} {'value' if len(deprecated) == 1 else 'values'} of {f['name']} {'is' if len(deprecated) == 1 else 'are'} deprecated in {where}.", deprecated, f["name"])


def cmd_vocab(args):
    mapping, vocabs = vocabularies()
    if not args.name:
        rows = []
        for t, s in schemas().items():
            for f in s["fields"]:
                vname = field_vocabulary(f)
                if vname:
                    rows.append([f"{t}.{f['name']}", vname, vocabs[vname]["source"]])
        print(table_text(rows, ["field", "GBIF vocabulary", "copied from"]))
        return
    vname = args.name
    if "." in vname:
        t, fname = vname.split(".", 1)
        f = field_map(schema(t)).get(fname)
        vname = field_vocabulary(f) if f else None
        if not vname:
            sys.exit(f"GBIF uses no vocabulary for {args.name}.")
    v = next((x for k, x in vocabs.items() if k.lower() == vname.lower()), None)
    if not v:
        sys.exit(f"No pinned vocabulary {vname}. Run: dwcdp.py vocab")
    rows = [[c["name"] + (" (deprecated" + (f", use {c['replacedBy']}" if c["replacedBy"] else "") + ")" if c["deprecated"] else ""),
             ", ".join(x for x in c["labels"] + c["alternativeLabels"] if x != c["name"])] for c in v["concepts"]]
    print(f"{v['vocabulary']} ({v['source']})\n")
    print(table_text(rows, ["concept", "labels"]))


# ---------------------------------------------------------------- database

def connect(path, read_only=False):
    try:
        import duckdb
    except ImportError:
        sys.exit("This needs the duckdb Python package: python3 -m pip install duckdb")
    if read_only and not os.path.exists(path):
        sys.exit(f"No database at {path}. Start with: dwcdp.py init <tables>")
    return duckdb.connect(path, read_only=read_only)


def q(ident):
    return '"' + ident.replace('"', '""') + '"'


def lit(value):
    return "'" + str(value).replace("'", "''") + "'"


def db_tables(con):
    rows = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name").fetchall()
    return [r[0] for r in rows]


def db_columns(con, table):
    rows = con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position", [table]).fetchall()
    return [r[0] for r in rows]


def count(con, sql):
    return con.execute(sql).fetchone()[0]


def dwc_tables_in(con):
    """{dwc name: row count} for the DwC-DP tables in the database."""
    out = {}
    for t in db_tables(con):
        if dwc_name(t) in schemas():
            out[dwc_name(t)] = count(con, f"SELECT count(*) FROM {q(t)}")
    return out


def create_table_sql(s):
    cols = ",\n  ".join(f"{q(f['name'])} {SQL_TYPES.get(f['type'], 'VARCHAR')}" for f in s["fields"])
    return f"CREATE TABLE IF NOT EXISTS {q(db_name(s['name']))} (\n  {cols}\n)"


# ---------------------------------------------------------------- output

def table_text(rows, header):
    rows = [["" if v is None else str(v) for v in r] for r in rows]
    widths = [min(max([len(h)] + [len(r[i]) for r in rows]), 60) for i, h in enumerate(header)]
    clip = lambda v, w: v if len(v) <= w else v[: w - 1] + "…"
    line = lambda r: "  ".join(clip(v, w).ljust(w) for v, w in zip(r, widths)).rstrip()
    return "\n".join([line(header), line(["-" * w for w in widths])] + [line(r) for r in rows])


# ---------------------------------------------------------------- schema commands

def cmd_tables(args):
    in_db = {}
    if args.db and os.path.exists(args.db):
        in_db = dwc_tables_in(connect(args.db, read_only=True))
    rows = []
    for name, s in schemas().items():
        targets = sorted({t for _, _, t, _ in keys(s, "foreignKeys") if t != name})
        mark = f"{in_db[name]} rows" if name in in_db else ""
        rows.append([name, first_sentence(s.get("description"), 90), ", ".join(targets), mark])
    print(table_text(rows, ["table", "what it holds", "points to", "in database"]))


def cmd_describe(args):
    s = schema(args.table)
    name = s["name"]
    fm = field_map(s)
    if args.field:
        f = fm.get(args.field)
        if not f:
            sys.exit(f"{name} has no field '{args.field}'. Run: dwcdp.py describe {name}")
        print(f"{name}.{f['name']} — {f['title']} ({f['type']})")
        for k in ("description", "notes", "examples", "dcterms:isVersionOf"):
            if f.get(k):
                print(f"\n{k}: {f[k]}")
        if constraints(f):
            print(f"\nconstraints: {json.dumps(constraints(f))}")
        return
    print(f"{name} — {s['title']}\n\n{s.get('description', '')}")
    if s.get("notes"):
        print(f"\nNotes: {s['notes']}")
    if s.get("examples"):
        print(f"\nExamples: {s['examples']}")
    print()
    if s.get("primaryKey"):
        print(f"Primary key: {s['primaryKey']} (a key for this package; MAY be changed when the data are aggregated)")
    if s.get("weakPrimaryKey"):
        print(f"Public identifier: {s['weakPrimaryKey']} (MUST be kept as is when the data are aggregated)")
    fks = keys(s, "foreignKeys")
    if fks:
        print("\nPoints to (foreign keys, must match a row in the package):")
        for field, pred, target, tfield in fks:
            print(f"  {field} → {target}.{tfield}  ({name} {pred} {target}){'  [itself]' if target == name else ''}")
    wfks = keys(s, "weakForeignKeys")
    if wfks:
        print("\nMay refer to (identifiers, can be outside the package):")
        for field, pred, target, tfield in wfks:
            print(f"  {field} → {target}.{tfield}  ({pred})")
    back = referenced_by(name)
    if back:
        print("\nPointed to by:")
        for t, field, pred in back:
            print(f"  {t}.{field}  ({t} {pred} {name})")
    fk_fields = {f: t for f, _, t, _ in fks}
    wfk_fields = {f: t for f, _, t, _ in wfks}
    rows = []
    for f in s["fields"]:
        c = constraints(f)
        flags = []
        if f["name"] == s.get("primaryKey"):
            flags.append("primary key")
        if f["name"] == s.get("weakPrimaryKey"):
            flags.append("public id")
        if f["name"] in fk_fields:
            flags.append(f"→ {fk_fields[f['name']]}")
        if f["name"] in wfk_fields:
            flags.append(f"id of {wfk_fields[f['name']]}")
        if c.get("required"):
            flags.append("required")
        if c.get("unique") and f["name"] != s.get("primaryKey"):
            flags.append("unique")
        if "minimum" in c or "maximum" in c:
            flags.append(f"{c.get('minimum', '')}..{c.get('maximum', '')}")
        rows.append([f["name"], f["type"], ", ".join(flags), first_sentence(f.get("description"), 100)])
    print(f"\nFields ({len(rows)}):")
    print(table_text(rows, ["field", "type", "", "description"]))
    print(f"\nMore on one field: dwcdp.py describe {name} --field <name>")


def fill_order(names):
    """names ordered so that every table comes after the tables it points to (self references
    ignored). Tables that point to each other keep their alphabetical order and are returned in
    the second list."""
    names = sorted(set(names))
    deps = {n: {t for _, _, t, _ in keys(schemas()[n], "foreignKeys") if t != n and t in names} for n in names}
    ordered, cycle = [], []
    while deps:
        ready = sorted(n for n, d in deps.items() if not d - set(ordered))
        if not ready:
            cycle = sorted(deps)
            break
        ordered += ready
        for n in ready:
            del deps[n]
    return ordered, cycle


def cmd_order(args):
    names = [schema(t)["name"] for t in args.tables] if args.tables else list(schemas())
    if not args.tables and args.db and os.path.exists(args.db):
        names = list(dwc_tables_in(connect(args.db, read_only=True))) or names
    ordered, cycle = fill_order(names)
    for i, n in enumerate(ordered, 1):
        targets = sorted({t for _, _, t, _ in keys(schemas()[n], "foreignKeys") if t != n and t in names})
        print(f"{i:3}. {n}" + (f"  (after {', '.join(targets)})" if targets else ""))
    if cycle:
        print(f"These point to each other; fill them together: {', '.join(cycle)}")


def cmd_find_term(args):
    needle = args.text.lower()
    hits = []
    for t, s in schemas().items():
        for f in s["fields"]:
            n = f["name"].lower()
            if n == needle:
                rank = 0
            elif needle in n:
                rank = 1
            elif needle in (f.get("title") or "").lower():
                rank = 2
            elif needle in (f.get("description") or "").lower():
                rank = 3
            elif args.notes and needle in (f.get("notes") or "").lower():
                rank = 4
            else:
                continue
            hits.append((rank, t, f))
    if not hits:
        print(f"No DwC-DP field mentions '{args.text}'." + ("" if args.notes else " Try --notes to search the usage notes too."))
        return
    hits.sort(key=lambda h: (h[0], h[1], h[2]["name"]))
    rows = [[f"{t}.{f['name']}", first_sentence(f.get("description"), 110)] for _, t, f in hits[: args.limit]]
    print(table_text(rows, ["table.field", "description"]))
    if len(hits) > args.limit:
        print(f"\n{len(hits) - args.limit} more; use --limit")


# ---------------------------------------------------------------- database commands

def cmd_init(args):
    names = [schema(t)["name"] for t in args.tables]
    con = connect(args.db)
    existing = set(db_tables(con))
    for n in names:
        con.execute(create_table_sql(schema(n)))
        print(f"{'exists ' if db_name(n) in existing else 'created'}  {db_name(n)}")
    missing = sorted({t for n in names for _, _, t, _ in keys(schema(n), "foreignKeys") if db_name(t) not in existing and t not in names})
    if missing:
        print(f"\nThese tables can be pointed to from the ones above, and are not in the database: {', '.join(missing)}.\n"
              "Add them only if the data have something for them.")


def cmd_load(args):
    path = os.path.abspath(args.file)
    if not os.path.exists(path):
        sys.exit(f"No file {args.file}")
    base = args.as_name or re.sub(r"[^0-9a-zA-Z]+", "_", os.path.splitext(os.path.basename(path))[0]).strip("_").lower()
    table = base if base.startswith("src_") else f"src_{base}"
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext == "gz":
        ext = os.path.splitext(path[:-3])[1].lower().lstrip(".")
    con = connect(args.db)
    if ext in ("csv", "tsv", "txt", "tab"):
        opts = ["header = true", "all_varchar = true", "sample_size = -1"]
        if args.sep:
            opts.append(f"delim = {lit(args.sep.encode().decode('unicode_escape'))}")
        elif ext in ("tsv", "tab"):
            opts.append("delim = '\\t'")
        src = f"read_csv({lit(path)}, {', '.join(opts)})"
    elif ext in ("xlsx",):
        src = f"read_xlsx({lit(path)}, all_varchar = true{', sheet = ' + lit(args.sheet) if args.sheet else ''})"
    elif ext == "parquet":
        src = f"read_parquet({lit(path)})"
    elif ext in ("json", "ndjson", "jsonl"):
        src = f"read_json_auto({lit(path)})"
    else:
        sys.exit(f"Don't know how to read .{ext}. Save it as CSV or TSV and load that.")
    try:
        con.execute(f"CREATE OR REPLACE TABLE {q(table)} AS SELECT * FROM {src}")
    except Exception as e:
        hint = " Reading .xlsx needs DuckDB's excel extension; if it can't be installed, save the sheet as CSV." if ext == "xlsx" else ""
        sys.exit(f"Could not read {args.file}: {e}{hint}")
    n = count(con, f"SELECT count(*) FROM {q(table)}")
    cols = db_columns(con, table)
    print(f"Loaded {n} rows, {len(cols)} columns, as {table}.\nColumns: {', '.join(cols)}")


def dwca_text(value, default):
    """A meta.xml delimiter attribute: '\\t' means a tab, '' means none."""
    if value is None:
        return default
    return value.replace("\\t", "\t").replace("\\n", "\n").replace("\\r", "\r")


def cmd_load_dwca(args):
    import tempfile
    import xml.etree.ElementTree as ET
    import zipfile

    src = os.path.abspath(args.archive)
    tmp = None
    if os.path.isfile(src) and zipfile.is_zipfile(src):
        tmp = tempfile.mkdtemp(prefix="dwca-")
        with zipfile.ZipFile(src) as z:
            for member in z.namelist():
                target = os.path.realpath(os.path.join(tmp, member))
                if not target.startswith(os.path.realpath(tmp) + os.sep):
                    sys.exit(f"{args.archive} has an entry outside the archive folder: {member}")
            z.extractall(tmp)
        root = tmp
    elif os.path.isdir(src):
        root = src
    else:
        sys.exit(f"{args.archive} is neither a Darwin Core Archive (.zip) nor a folder.")
    try:
        meta = os.path.join(root, "meta.xml")
        if not os.path.exists(meta):
            nested = [d for d in os.listdir(root) if os.path.exists(os.path.join(root, d, "meta.xml"))]
            if len(nested) != 1:
                sys.exit(f"No meta.xml in {args.archive}. A Darwin Core Archive describes its files in meta.xml.")
            root = os.path.join(root, nested[0])
            meta = os.path.join(root, "meta.xml")
        ns = {"d": "http://rs.tdwg.org/dwc/text/"}
        tree = ET.parse(meta).getroot()
        parts = [("core", e) for e in tree.findall("d:core", ns)] + [("extension", e) for e in tree.findall("d:extension", ns)]
        if not parts:
            sys.exit("meta.xml lists no core file.")
        con = connect(args.db)
        for kind, e in parts:
            location = e.find("d:files/d:location", ns).text.strip()
            row_type = e.get("rowType", "")
            base = re.sub(r"[^0-9a-zA-Z]+", "_", row_type.rstrip("/").split("/")[-1]).lower() or os.path.splitext(location)[0]
            table = f"src_dwca_{base}"
            delim = dwca_text(e.get("fieldsTerminatedBy"), ",")
            quote = dwca_text(e.get("fieldsEnclosedBy"), '"')
            skip = int(e.get("ignoreHeaderLines") or 0)
            options = ["header = false", "all_varchar = true", f"skip = {skip}", f"delim = {lit(delim)}", "sample_size = -1", "null_padding = true"]
            options.append(f"quote = {lit(quote)}" if quote else "quote = ''")
            if (e.get("encoding") or "UTF-8").upper().replace("-", "") not in ("UTF8",):
                options.append(f"encoding = {lit(e.get('encoding'))}")
            con.execute(f"CREATE OR REPLACE TEMP TABLE dwca_raw AS SELECT * FROM read_csv({lit(os.path.join(root, location))}, {', '.join(options)})")
            raw = db_columns_temp(con, "dwca_raw")
            select, names = [], []
            key = e.find("d:id", ns) if kind == "core" else e.find("d:coreid", ns)
            if key is not None and key.get("index") is not None:
                select.append(f"{q(raw[int(key.get('index'))])} AS {q('id' if kind == 'core' else 'coreid')}")
                names.append("id" if kind == "core" else "coreid")
            for fe in e.findall("d:field", ns):
                term = fe.get("term", "")
                name = term.rstrip("/").split("/")[-1].split("#")[-1]
                if name in names:
                    name = re.sub(r"[^0-9a-zA-Z]+", "_", term.split("//")[-1]).strip("_")
                if fe.get("index") is not None:
                    i = int(fe.get("index"))
                    if i >= len(raw):
                        sys.exit(f"meta.xml maps {term} to column {i}, and {location} has {len(raw)} columns.")
                    expr = q(raw[i])
                    if fe.get("default") is not None:
                        expr = f"coalesce(nullif({expr}, ''), {lit(fe.get('default'))})"
                else:
                    expr = lit(fe.get("default", ""))
                select.append(f"{expr} AS {q(name)}")
                names.append(name)
            con.execute(f"CREATE OR REPLACE TABLE {q(table)} AS SELECT {', '.join(select)} FROM dwca_raw")
            con.execute("DROP TABLE dwca_raw")
            n = count(con, f"SELECT count(*) FROM {q(table)}")
            print(f"{kind:9} {location}: {n} rows as {table} ({row_type})\n          columns: {', '.join(names)}")
        eml = os.path.join(root, tree.get("metadata") or "eml.xml")
        if os.path.exists(eml):
            print(f"\nThe archive has metadata in {os.path.relpath(eml, root)}. Read it for Stage 6; it is not copied anywhere.")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def db_columns_temp(con, table):
    return [r[0] for r in con.execute(f"DESCRIBE {q(table)}").fetchall()]


def cmd_run(args):
    with open(args.sql, encoding="utf-8") as fh:
        script = fh.read()
    con = connect(args.db)
    before = dwc_tables_in(con)
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute(script)
        con.execute("COMMIT")
    except Exception as e:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        sys.exit(f"{args.sql} failed, and nothing was changed: {e}")
    after = dwc_tables_in(con)
    rows = [[t, before.get(t, "-"), n] for t, n in after.items()]
    print(f"Ran {args.sql}.")
    if rows:
        print(table_text(rows, ["table", "rows before", "rows after"]))


def cmd_sql(args):
    con = connect(args.db, read_only=True)
    try:
        cur = con.execute(args.query)
    except Exception as e:
        sys.exit(str(e))
    if cur.description is None:
        return
    header = [d[0] for d in cur.description]
    rows = cur.fetchmany(args.limit)
    print(table_text(rows, header))


def cmd_status(args):
    con = connect(args.db, read_only=True)
    rows = []
    for t in db_tables(con):
        kind = "DwC-DP" if dwc_name(t) in schemas() else ("source" if t.startswith("src_") else "other")
        rows.append([t, kind, count(con, f"SELECT count(*) FROM {q(t)}")])
    print(table_text(rows, ["table", "kind", "rows"]) if rows else "The database is empty.")


# ---------------------------------------------------------------- checks

class Report:
    def __init__(self):
        self.items = []

    def add(self, level, table, message, examples=None, field=None):
        self.items.append({"level": level, "table": table, "field": field, "message": message, "examples": examples or []})

    def error(self, *a, **k):
        self.add("error", *a, **k)

    def warning(self, *a, **k):
        self.add("warning", *a, **k)

    @property
    def errors(self):
        return [i for i in self.items if i["level"] == "error"]

    def print(self, as_json=False, ok_text="No problems found."):
        if as_json:
            print(json.dumps({"errors": len(self.errors), "items": self.items}, indent=2, default=str))
            return
        if not self.items:
            print(ok_text)
            return
        for level, title in (("error", "Must be fixed"), ("warning", "Worth checking")):
            items = [i for i in self.items if i["level"] == level]
            if not items:
                continue
            print(f"{title} ({len(items)}):")
            for i in items:
                shown = i["examples"][:EXAMPLES_SHOWN]
                more = f" and {len(i['examples']) - len(shown)} more" if len(i["examples"]) > len(shown) else ""
                ex = f" For example: {', '.join(repr(str(e)) for e in shown)}{more}." if shown else ""
                print(f"  - {i['table']}: {i['message']}{ex}")
            print()


def have(n, total=None):
    """'1 row has' / '3 rows have', or '1 of 4 rows has'."""
    noun = "row" if (total or n) == 1 else "rows"
    verb = "has" if n == 1 else "have"
    return f"{n} of {total} {noun} {verb}" if total is not None else f"{n} {noun} {verb}"


def examples(con, sql):
    return [r[0] for r in con.execute(f"{sql} LIMIT {EXAMPLES_SHOWN}").fetchall()]


def check_tables(con, present, report):
    """Relational and field checks. present: {dwc name: (db table, [columns], rows)}."""
    for name, (table, cols, rows) in present.items():
        s = schemas()[name]
        fm = field_map(s)
        if rows == 0:
            report.warning(name, "has no rows. Leave it out, or fill it.")
            continue
        T = q(table)
        for f in s["fields"]:
            fname, c = f["name"], constraints(f)
            if fname not in cols:
                if c.get("required"):
                    report.error(name, f"the required field {fname} is missing.", field=fname)
                continue
            F = q(fname)
            if c.get("required"):
                n = count(con, f"SELECT count(*) FROM {T} WHERE {F} IS NULL OR trim(CAST({F} AS VARCHAR)) = ''")
                if n:
                    report.error(name, f"{have(n, rows)} no {fname}, which is required.", field=fname)
            if c.get("unique"):
                n = count(con, f"SELECT count(*) FROM (SELECT {F} FROM {T} WHERE {F} IS NOT NULL GROUP BY {F} HAVING count(*) > 1)")
                if n:
                    ex = examples(con, f"SELECT {F} FROM {T} WHERE {F} IS NOT NULL GROUP BY {F} HAVING count(*) > 1 ORDER BY 1")
                    what = "the primary key" if fname == s.get("primaryKey") else "a field that must be unique"
                    report.error(name, f"{n} {'value' if n == 1 else 'values'} of {fname} ({what}) {'occurs' if n == 1 else 'occur'} more than once.", ex, fname)
            for bound, op in (("minimum", "<"), ("maximum", ">")):
                if bound in c:
                    n = count(con, f"SELECT count(*) FROM {T} WHERE TRY_CAST({F} AS DOUBLE) {op} {float(c[bound])}")
                    if n:
                        ex = examples(con, f"SELECT DISTINCT {F} FROM {T} WHERE TRY_CAST({F} AS DOUBLE) {op} {float(c[bound])}")
                        report.error(name, f"{have(n)} {fname} {'below' if op == '<' else 'above'} its {bound} of {c[bound]}.", ex, fname)

        for fname, pred, target, tfield in keys(s, "foreignKeys"):
            if fname not in cols:
                continue
            F = q(fname)
            used = count(con, f"SELECT count(*) FROM {T} WHERE {F} IS NOT NULL")
            if not used:
                continue
            tgt = present.get(target)
            if not tgt or tgt[2] == 0 or tfield not in tgt[1]:
                report.error(name, f"{have(used)} a value in {fname}, so the package needs the {target} table with {tfield}, and it {'is empty' if tgt else 'is not there'}.", field=fname)
                continue
            sub = f"SELECT {q(tfield)} FROM {q(tgt[0])} WHERE {q(tfield)} IS NOT NULL"
            bad_sql = f"SELECT DISTINCT {F} FROM {T} WHERE {F} IS NOT NULL AND {F} NOT IN ({sub})"
            n = count(con, f"SELECT count(*) FROM {T} WHERE {F} IS NOT NULL AND {F} NOT IN ({sub})")
            if n:
                report.error(name, f"{have(n)} a value in {fname} that matches no {tfield} in {target} ({name} {pred} {target}).", examples(con, bad_sql + " ORDER BY 1"), fname)

        for fname, pred, target, tfield in keys(s, "weakForeignKeys"):
            tgt = present.get(target)
            if fname not in cols or not tgt or tgt[2] == 0 or tfield not in tgt[1]:
                continue
            F = q(fname)
            sub = f"SELECT {q(tfield)} FROM {q(tgt[0])} WHERE {q(tfield)} IS NOT NULL"
            n = count(con, f"SELECT count(*) FROM {T} WHERE {F} IS NOT NULL AND {F} NOT IN ({sub})")
            if n:
                ex = examples(con, f"SELECT DISTINCT {F} FROM {T} WHERE {F} IS NOT NULL AND {F} NOT IN ({sub}) ORDER BY 1")
                report.warning(name, f"{have(n)} a value in {fname} that is not a {tfield} in this package's {target} table. That is allowed if it identifies a {target} elsewhere; otherwise it is a typo.", ex, fname)

        # The conceptual model (https://dwc.tdwg.org/cm/, 2.5) says an identification is based on
        # one kind of evidence; the schema marks those foreign keys with the predicate "based on".
        evidence = [f for f, pred, _, _ in keys(s, "foreignKeys") if pred == "based on" and f in cols]
        if len(evidence) > 1:
            several = " + ".join(f"(CASE WHEN {q(f)} IS NOT NULL THEN 1 ELSE 0 END)" for f in evidence)
            n = count(con, f"SELECT count(*) FROM {T} WHERE {several} > 1")
            if n:
                report.warning(name, f"{n} {'row is' if n == 1 else 'rows are'} based on more than one kind of evidence ({', '.join(evidence)}). The Darwin Core conceptual model has an identification based on one.")

        for fname, pred, target, tfield in keys(s, "foreignKeys"):
            if target == name and fname in cols and s.get("primaryKey") in cols:
                n = count(con, f"SELECT count(*) FROM {T} WHERE {q(fname)} IS NOT NULL AND {q(fname)} = {q(s['primaryKey'])}")
                if n:
                    report.error(name, f"{n} {'row points' if n == 1 else 'rows point'} to itself in {fname}.", field=fname)

        check_vocabularies(con, name, table, cols, report)


def cmd_validate(args):
    con = connect(args.db, read_only=True)
    report = Report()
    present = {}
    for name, rows in dwc_tables_in(con).items():
        present[name] = (db_name(name), db_columns(con, db_name(name)), rows)
    if not present:
        sys.exit("The database has no DwC-DP tables yet. Start with: dwcdp.py init <tables>")
    check_tables(con, present, report)
    report.print(args.json, "No problems found in " + ", ".join(f"{t} ({r[2]} rows)" for t, r in present.items()) + ".")
    sys.exit(1 if report.errors else 0)


def cmd_diagram(args):
    con = connect(args.db, read_only=True)
    present = dwc_tables_in(con)
    names = list(present) if args.all else [t for t, n in present.items() if n]
    if args.tables:
        names = [schema(t)["name"] for t in args.tables]
    lines = ["erDiagram"]
    used_by = {}
    for n in names:
        s = schema(n)
        cols = db_columns(con, db_name(n)) if db_name(n) in db_tables(con) else [f["name"] for f in s["fields"]]
        used = [c for c in cols if c in field_map(s) and (db_name(n) not in db_tables(con) or count(con, f"SELECT count(*) FROM {q(db_name(n))} WHERE {q(c)} IS NOT NULL"))]
        used_by[n] = set(used)
        fk_fields = {f for f, _, _, _ in keys(s, "foreignKeys")}
        lines.append(f"  {db_name(n)} {{")
        for c in used:
            tag = " PK" if c == s.get("primaryKey") else (" FK" if c in fk_fields else "")
            lines.append(f"    {field_map(s)[c]['type']} {c}{tag}")
        lines.append("  }")
    for n in names:
        s = schema(n)
        for fname, pred, target, _ in keys(s, "foreignKeys"):
            if target in names and fname in used_by[n]:
                lines.append(f'  {db_name(n)} }}o--o| {db_name(target)} : "{pred or fname}"')
    print("\n".join(lines))


# ---------------------------------------------------------------- package

def resource_schema(s, cols):
    """The vendored table schema reduced to the columns the package has, field descriptors copied
    verbatim, in schema order."""
    out = {k: v for k, v in s.items() if k not in ("fields", "primaryKey", "foreignKeys", "weakPrimaryKey", "weakForeignKeys", "url")}
    out["fields"] = [f for f in s["fields"] if f["name"] in cols]
    if s.get("primaryKey") in cols:
        out["primaryKey"] = s["primaryKey"]
    fks = [k for k in s.get("foreignKeys") or [] if as_list(k["fields"])[0] in cols]
    if fks:
        out["foreignKeys"] = fks
    if s.get("weakPrimaryKey") in cols:
        out["weakPrimaryKey"] = s["weakPrimaryKey"]
    wfks = [k for k in s.get("weakForeignKeys") or [] if as_list(k["fields"])[0] in cols]
    if wfks:
        out["weakForeignKeys"] = wfks
    return out


def cmd_package(args):
    con = connect(args.db, read_only=True)
    present = {n: (db_name(n), db_columns(con, db_name(n)), r) for n, r in dwc_tables_in(con).items() if r}
    if not present:
        sys.exit("There are no DwC-DP rows to package yet.")
    report = Report()
    check_tables(con, present, report)
    if report.errors:
        report.print()
        sys.exit("Not packaged: fix the problems above first (dwcdp.py validate shows them again).")
    out = os.path.abspath(args.out)
    if os.path.exists(out) and os.listdir(out):
        if not args.overwrite:
            sys.exit(f"{args.out} is not empty. Choose another folder, or add --overwrite to replace it.")
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    resources = []
    for name, (table, cols, rows) in present.items():
        s = schemas()[name]
        fm = field_map(s)
        unknown = [c for c in cols if c not in fm]
        if unknown:
            sys.exit(f"{table} has columns that are not DwC-DP fields of {name}: {', '.join(unknown)}")
        used = [f["name"] for f in s["fields"] if f["name"] in cols and (constraints(f).get("required") or count(con, f"SELECT count(*) FROM {q(table)} WHERE {q(f['name'])} IS NOT NULL"))]
        path = f"{name}.csv"
        select = ", ".join(q(c) for c in used)
        order = f" ORDER BY {q(s['primaryKey'])}" if s.get("primaryKey") in used else ""
        con.execute(f"COPY (SELECT {select} FROM {q(table)}{order}) TO {lit(os.path.join(out, path))} (HEADER, DELIMITER ',', QUOTE '\"', ESCAPE '\"')")
        resources.append({
            "name": name,
            "path": path,
            "profile": "tabular-data-resource",
            "format": "csv",
            "mediatype": "text/csv",
            "encoding": "utf-8",
            "schema": resource_schema(s, used),
        })
        print(f"{path}: {rows} rows, {len(used)} fields")
    descriptor = {"profile": PROFILE_URL}
    for key in ("id", "title", "version"):
        if getattr(args, key):
            descriptor[key] = getattr(args, key)
    descriptor["created"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    descriptor["resources"] = resources
    with open(os.path.join(out, "datapackage.json"), "w", encoding="utf-8") as fh:
        json.dump(descriptor, fh, indent=2, ensure_ascii=False)
    if args.eml:
        shutil.copyfile(args.eml, os.path.join(out, "eml.xml"))
    print(f"\nWrote {args.out}: datapackage.json{', eml.xml' if args.eml else ''} and {len(resources)} tables.")
    for w in report.items:
        print(f"  note, {w['table']}: {w['message']}")


def cmd_check(args):
    root = os.path.abspath(args.path)
    dp_path = os.path.join(root, "datapackage.json")
    if not os.path.exists(dp_path):
        sys.exit(f"No datapackage.json in {args.path}")
    with open(dp_path, encoding="utf-8") as fh:
        dp = json.load(fh)
    report = Report()
    profile = dp.get("profile") or ""
    if not re.match(r"^https?://rs\.tdwg\.org/dwc-dp/[^/]+/dwc-dp-profile\.json$", profile):
        report.error("datapackage.json", f"profile is {profile!r}; a DwC-DP names a versioned profile on rs.tdwg.org, such as {PROFILE_URL}.")
    elif f"/dwc-dp/{VERSION}/" not in profile:
        report.error("datapackage.json", f"profile is {profile}, and this tool checks DwC-DP {VERSION}.")
    resources = dp.get("resources") or []
    if not resources:
        report.error("datapackage.json", "has no resources.")
    con = connect(":memory:")
    present = {}
    for r in resources:
        name = r.get("name", "")
        if name not in schemas():
            continue
        s = schemas()[name]
        fm = field_map(s)
        if r.get("profile") != "tabular-data-resource":
            report.error(name, "resource profile must be tabular-data-resource.")
        if r.get("mediatype") != "text/csv":
            report.error(name, f"mediatype is {r.get('mediatype')!r}; DwC-DP tables must say text/csv.")
        rs = r.get("schema")
        if not isinstance(rs, dict):
            report.error(name, "schema must be the table schema itself, not a reference to one.")
            continue
        fields = rs.get("fields") or []
        names = [f.get("name") for f in fields]
        unknown = [f.get("name") for f in fields if f.get("name") not in fm]
        if unknown:
            report.error(name, f"{len(unknown)} of its {len(fields)} fields {'is' if len(unknown) == 1 else 'are'} not DwC-DP {VERSION} fields of {name}.", unknown)
        for k in ("type", "dcterms:isVersionOf"):
            differ = [f["name"] for f in fields if f.get("name") in fm and f.get(k) != fm[f["name"]].get(k)]
            if differ:
                report.error(name, f"{len(differ)} {'field has' if len(differ) == 1 else 'fields have'} a {k} other than the DwC-DP schema's (field descriptors must be copied from it).", differ)
        bad = bool(unknown)
        pk = rs.get("primaryKey")
        if pk is not None and as_list(pk) != as_list(s.get("primaryKey")):
            report.error(name, f"primaryKey is {pk!r}; the DwC-DP schema defines {s.get('primaryKey')!r}.")
        bad_fks = []
        allowed = {(as_list(k["fields"])[0], (k.get("reference") or {}).get("resource") or name, as_list((k.get("reference") or {}).get("fields"))[0]) for k in s.get("foreignKeys") or []}
        declared = set()
        for k in rs.get("foreignKeys") or []:
            key = (as_list(k.get("fields"))[0], (k.get("reference") or {}).get("resource") or name, as_list((k.get("reference") or {}).get("fields"))[0])
            declared.add(key[0])
            if key not in allowed:
                bad_fks.append(f"{key[0]} → {key[1]}.{key[2]}")
        if bad_fks:
            report.error(name, f"{len(bad_fks)} {'foreign key is not one' if len(bad_fks) == 1 else 'foreign keys are not ones'} the DwC-DP schema defines.", bad_fks)
        for f, _, t, tf in keys(s, "foreignKeys"):
            if f in names and f not in declared:
                report.error(name, f"has the field {f} but does not declare its foreign key to {t}.{tf}.", field=f)
        path = os.path.join(root, r.get("path") or "")
        if not r.get("path") or not os.path.exists(path):
            report.error(name, f"its file {r.get('path')!r} is not in the package.")
            continue
        if bad:
            continue
        dialect = r.get("dialect") or {}
        delim = dialect.get("delimiter") or ("\t" if (r.get("format") == "tsv" or path.endswith((".tsv", ".tsv.gz"))) else ",")
        header_ok = dialect.get("header", True)
        table = f"pkg_{db_name(name)}"
        quote = dialect.get("quoteChar", '"')
        options = [f"header = {str(header_ok).lower()}", "all_varchar = true", f"delim = {lit(delim)}",
                   f"quote = {lit(quote)}", f"escape = {lit(quote if dialect.get('doubleQuote', True) else dialect.get('escapeChar', ''))}",
                   "sample_size = -1"]
        if not header_ok:
            options.append("names = [" + ", ".join(lit(n) for n in names) + "]")
        try:
            con.execute(f"CREATE TABLE {q(table)} AS SELECT * FROM read_csv({lit(path)}, {', '.join(options)})")
        except Exception as e:
            reason = str(e).split("\n")[0].replace(path, r["path"])
            report.error(name, f"{r['path']} could not be read as CSV ({reason}). A row may have more or fewer columns than the header, or an unclosed quote.")
            continue
        cols = db_columns(con, table)
        if cols != names:
            report.error(name, f"the file's columns do not match the schema's fields in order and number (file: {len(cols)}, schema: {len(names)}).", [c for c in cols if c not in names][:EXAMPLES_SHOWN] or None)
            continue
        rows = count(con, f"SELECT count(*) FROM {q(table)}")
        for f in fields:
            sql_type = SQL_TYPES.get(fm[f["name"]]["type"])
            if sql_type and sql_type != "VARCHAR":
                F = q(f["name"])
                cast = f"TRY_CAST(trim({F}) AS {sql_type})"
                n = count(con, f"SELECT count(*) FROM {q(table)} WHERE trim({F}) <> '' AND {cast} IS NULL")
                if n:
                    report.error(name, f"{n} {'value' if n == 1 else 'values'} of {f['name']} {'is' if n == 1 else 'are'} not of type {fm[f['name']]['type']}.", examples(con, f"SELECT DISTINCT {F} FROM {q(table)} WHERE trim({F}) <> '' AND {cast} IS NULL"), f["name"])
        con.execute(f"UPDATE {q(table)} SET " + ", ".join(f"{q(c)} = NULLIF({q(c)}, '')" for c in cols))
        present[name] = (table, cols, rows)
    unknown = [r.get("name") for r in resources if r.get("name") not in schemas() and r.get("profile") == "tabular-data-resource"]
    if unknown:
        report.warning("datapackage.json", f"has tables that are not DwC-DP {VERSION} tables, and they were not checked: {', '.join(map(str, unknown))}.")
    check_tables(con, present, report)
    report.print(args.json, f"No problems found in {args.path}: " + ", ".join(f"{t} ({r[2]} rows)" for t, r in present.items()) + ".")
    sys.exit(1 if report.errors else 0)


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=os.environ.get("DWCDP_DB", "dwcdp.duckdb"), help="working database (default ./dwcdp.duckdb)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("tables", help="list the DwC-DP tables").set_defaults(func=cmd_tables)
    s = sub.add_parser("describe", help="fields, keys and relations of a table")
    s.add_argument("table")
    s.add_argument("--field", help="show everything about one field")
    s.set_defaults(func=cmd_describe)
    s = sub.add_parser("order", help="the order to fill tables in: tables pointed to come first")
    s.add_argument("tables", nargs="*", help="default: the DwC-DP tables in the database, or all")
    s.set_defaults(func=cmd_order)
    s = sub.add_parser("find-term", help="search field names and descriptions")
    s.add_argument("text")
    s.add_argument("--notes", action="store_true", help="also search usage notes")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_find_term)

    s = sub.add_parser("vocab", help="GBIF vocabularies: which fields use them, or one vocabulary's concepts")
    s.add_argument("name", nargs="?", help="a vocabulary, e.g. LifeStage, or a field, e.g. occurrence.lifeStage")
    s.set_defaults(func=cmd_vocab)
    s = sub.add_parser("init", help="create DwC-DP tables in the database")
    s.add_argument("tables", nargs="+")
    s.set_defaults(func=cmd_init)
    s = sub.add_parser("load", help="stage a source file as a src_ table (all values as text)")
    s.add_argument("file")
    s.add_argument("--as", dest="as_name", help="table name (src_ is added)")
    s.add_argument("--sep", help="column separator, e.g. ';' or '\\t'")
    s.add_argument("--sheet", help="sheet of an .xlsx file")
    s.set_defaults(func=cmd_load)
    s = sub.add_parser("load-dwca", help="stage a Darwin Core Archive's core and extensions as src_dwca_ tables")
    s.add_argument("archive", help="the archive (.zip) or its unzipped folder")
    s.set_defaults(func=cmd_load_dwca)
    s = sub.add_parser("run", help="run a SQL file in one transaction")
    s.add_argument("sql")
    s.set_defaults(func=cmd_run)
    s = sub.add_parser("sql", help="run one read-only query and print the result")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_sql)
    sub.add_parser("status", help="tables in the database and their rows").set_defaults(func=cmd_status)
    s = sub.add_parser("validate", help="check the DwC-DP tables in the database")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_validate)
    s = sub.add_parser("diagram", help="Mermaid diagram of the tables in use")
    s.add_argument("tables", nargs="*")
    s.add_argument("--all", action="store_true", help="include empty tables")
    s.set_defaults(func=cmd_diagram)
    s = sub.add_parser("package", help="write the tables and datapackage.json to a folder")
    s.add_argument("out")
    s.add_argument("--eml", help="an eml.xml to include")
    s.add_argument("--id", help="dataset identifier, preferably a DOI")
    s.add_argument("--title")
    s.add_argument("--version", help="dataset version")
    s.add_argument("--overwrite", action="store_true")
    s.set_defaults(func=cmd_package)
    s = sub.add_parser("check", help="check a DwC-DP package on disk")
    s.add_argument("path")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
