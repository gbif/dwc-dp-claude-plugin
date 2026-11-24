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
  python3 dwcdp.py suggest src_samples         # which columns have a DwC-DP field, which don't
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

def table_text(rows, header, last=60):
    rows = [["" if v is None else str(v) for v in r] for r in rows]
    widths = [min(max([len(h)] + [len(r[i]) for r in rows]), last if i == len(header) - 1 else 60) for i, h in enumerate(header)]
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
        # Which Darwin Core term each staged column holds, so that suggest can match columns to
        # DwC-DP fields by term (dcterms:isVersionOf) instead of by name.
        con.execute("CREATE TABLE IF NOT EXISTS src_dwca_terms (source_table VARCHAR, column_name VARCHAR, term VARCHAR, row_type VARCHAR)")
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
                if not re.match(r"^[A-Za-z_]", name):
                    # A numbered term such as https://w3id.org/mixs/0000044: use the name of the
                    # DwC-DP field that is a version of it (target_gene), if there is one.
                    name = term_field_names().get(term, name)
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
            con.execute("DELETE FROM src_dwca_terms WHERE source_table = ?", [table])
            terms = [("id" if kind == "core" else "coreid", None)] if key is not None and key.get("index") is not None else []
            terms += [(n, fe.get("term")) for n, fe in zip(names[len(terms):], e.findall("d:field", ns))]
            for column_name, term in terms:
                con.execute("INSERT INTO src_dwca_terms VALUES (?, ?, ?, ?)", [table, column_name, term, row_type])
            con.execute("DROP TABLE dwca_raw")
            n = count(con, f"SELECT count(*) FROM {q(table)}")
            print(f"{kind:9} {location}: {n} {'row' if n == 1 else 'rows'} as {table} ({row_type})\n          columns: {', '.join(names)}")
        eml = os.path.join(root, tree.get("metadata") or "eml.xml")
        if os.path.exists(eml):
            print(f"\nThe archive has metadata in {os.path.relpath(eml, root)}. Read it for Stage 6; it is not copied anywhere.")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def term_field_names():
    """{term URI: a DwC-DP field name that is a version of it}."""
    out = {}
    for sch in schemas().values():
        for f in sch["fields"]:
            out.setdefault(f.get("dcterms:isVersionOf"), f["name"])
    return out


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


def normalise(name):
    return re.sub(r"[^0-9a-z]", "", name.lower())


# Darwin Core terms whose values name other organisms, and words in column names that often do:
# an interaction or relationship between organisms, not a measurement (references/interactions.md).
ASSOCIATION_TERMS = {"associatedTaxa", "associatedOccurrences", "associatedOrganisms"}
ASSOCIATION_WORDS = ("associat", "host", "prey", "predat", "parasit", "pollinat", "visited", "visitor", "symbio",
                     "mycorrhiz", "partner", "foodplant", "epiphyt", "interact")


def names_other_organism(col, term):
    if term and term.rsplit("/", 1)[-1] in ASSOCIATION_TERMS:
        return True
    return any(w in col.lower() for w in ASSOCIATION_WORDS)


def cmd_suggest(args):
    """For each column of a source table: the DwC-DP fields it could be, or a note that none
    matches, so it may be a measurement or fact for an assertion table."""
    con = connect(args.db, read_only=True)
    src = args.source if args.source in db_tables(con) else f"src_{args.source}"
    if src not in db_tables(con):
        sys.exit(f"No table {args.source} in the database. Run: dwcdp.py status")
    target = schema(args.table)["name"] if args.table else None
    by_name, by_title, all_fields = {}, {}, []
    for t, sch in schemas().items():
        if target and t != target:
            continue
        for f in sch["fields"]:
            by_name.setdefault(normalise(f["name"]), []).append(f"{t}.{f['name']}")
            by_title.setdefault(normalise(f.get("title") or ""), []).append(f"{t}.{f['name']}")
            all_fields.append((normalise(f["name"]), f"{t}.{f['name']}"))
    by_term = {}
    for t, sch in schemas().items():
        if target and t != target:
            continue
        for f in sch["fields"]:
            by_term.setdefault(f.get("dcterms:isVersionOf"), []).append(f"{t}.{f['name']}")
    known_terms = {}
    if "src_dwca_terms" in db_tables(con):
        known_terms = dict(con.execute("SELECT column_name, term FROM src_dwca_terms WHERE source_table = ? AND term IS NOT NULL", [src]).fetchall())
    rows = []
    for col in db_columns(con, src):
        C = q(col)
        values = con.execute(f"SELECT DISTINCT CAST({C} AS VARCHAR) FROM {q(src)} WHERE {C} IS NOT NULL AND trim(CAST({C} AS VARCHAR)) <> '' LIMIT 3").fetchall()
        filled = count(con, f"SELECT count(*) FROM {q(src)} WHERE {C} IS NOT NULL AND trim(CAST({C} AS VARCHAR)) <> ''")
        numeric = filled and count(con, f"SELECT count(*) FROM {q(src)} WHERE TRY_CAST(replace(trim(CAST({C} AS VARCHAR)), ',', '.') AS DOUBLE) IS NOT NULL") >= 0.9 * filled
        hits = by_name.get(normalise(col)) or by_title.get(normalise(col)) or []
        # Field names that contain the column's name, such as minimumDepthInMeters for "depth":
        # likely dedicated fields to check before anything goes in an assertion.
        words = [w for w in re.split(r"[^0-9a-z]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", col).lower()) if len(w) >= 3]
        maybe = sorted({ref for n, ref in all_fields for w in words if w in n},
                       key=lambda ref: (not ref.split(".")[0] == (target or ref.split(".")[0]), len(ref)))
        term = known_terms.get(col)
        if col in ("id", "coreid") and known_terms and term is None:
            note = "the archive's record key, linking extension rows to their core row; not a field"
        elif term:
            # A Darwin Core Archive column: its term says where it can go.
            by = by_term.get(term, [])
            if by:
                note = "by term: " + ", ".join(by[:5]) + (f" and {len(by) - 5} more" if len(by) > 5 else "")
            elif not filled:
                note = "(empty)"
            else:
                note = f"no DwC-DP field is a version of {term.rsplit('/', 1)[-1]}; see references/recipes/dwca.md"
        elif hits:
            note = ", ".join(hits[:4]) + (f" and {len(hits) - 4} more" if len(hits) > 4 else "")
        elif maybe and filled:
            note = "maybe " + ", ".join(maybe[:3]) + (f" ({len(maybe) - 3} more: find-term)" if len(maybe) > 3 else "") + "; else an assertion"
        elif not filled:
            note = "(empty)"
        else:
            assertion = f"{target}-assertion" if target and f"{target}-assertion" in schemas() else "an assertion table"
            note = (f"no field; looks like a measurement for {assertion}" if numeric
                    else f"no field; a fact for {assertion}, or try find-term")
        if filled and names_other_organism(col, term):
            note = ("names other organisms? then organism-interaction (references/interactions.md), not an assertion; "
                    + note)
        rows.append([col, ", ".join(str(v[0]) for v in values), note])
    print(table_text(rows, ["column", "values", "DwC-DP field"], last=130))
    if target and f"{target}-assertion" not in schemas():
        print(f"\n{target} has no assertion table. A measurement about it needs another home; ask the data holder.")
    print("\nA match by name is a suggestion, not a decision: check it with describe --field. For the others, "
          "try find-term with other words first. A column whose values name another organism (a host, a prey, a "
          "plant visited or grown on) is an interaction: see references/interactions.md. Measurements and facts: "
          "references/assertions.md.")


# ---------------------------------------------------------------- GRSciColl

GRSCICOLL_API = os.environ.get("DWCDP_GRSCICOLL_API", "https://api.gbif.org/v1/grscicoll")
GRSCICOLL_PAGE = "https://scientific-collections.gbif.org"
GRSCICOLL_COLUMNS = {"institutionCode": "institutionCode", "institutionID": "institutionId",
                     "collectionCode": "collectionCode", "collectionID": "collectionId"}


def grscicoll_get(path, params=None):
    import urllib.error
    import urllib.parse
    import urllib.request
    url = f"{GRSCICOLL_API}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=30) as r:
            return json.load(r)
    except (urllib.error.URLError, OSError, ValueError) as e:
        sys.exit(f"Could not reach GRSciColl ({url}): {e}. Nothing was changed.")


def grscicoll_entity(kind, key, cache):
    """An institution or collection, with every identifier GRSciColl holds for it."""
    if (kind, key) not in cache:
        d = grscicoll_get(f"{kind}/{key}")
        ids = [{"type": "GRSciColl page", "identifier": f"{GRSCICOLL_PAGE}/{kind}/{key}"},
               {"type": "GRSciColl key", "identifier": key}]
        for i in d.get("identifiers") or []:
            entry = {"type": i.get("type"), "identifier": i.get("identifier")}
            if entry not in ids:
                ids.append(entry)
        cache[(kind, key)] = {
            "kind": kind, "key": key, "code": d.get("code"), "name": d.get("name"), "active": d.get("active"),
            "country": (d.get("address") or {}).get("country") or (d.get("mailingAddress") or {}).get("country"),
            "institution": d.get("institutionName"), "alternativeCodes": [a["code"].strip() for a in d.get("alternativeCodes") or [] if (a.get("code") or "").strip()],
            "identifiers": ids}
    return cache[(kind, key)]


def grscicoll_lookup(query, cache):
    d = grscicoll_get("lookup", dict(query, verbose="true"))
    out = {}
    for kind, name in (("institution", "institutionMatch"), ("collection", "collectionMatch")):
        m = d.get(name) or {}
        entry = {"matchType": m.get("matchType"), "status": m.get("status"), "reasons": m.get("reasons") or [],
                 "match": grscicoll_entity(kind, m["entityMatched"]["key"], cache) if m.get("entityMatched") else None,
                 "alternatives": []}
        for a in ((d.get("alternativeMatches") or {}).get(f"{kind}Matches") or []):
            if a.get("entityMatched"):
                entry["alternatives"].append({"matchType": a.get("matchType"), "reasons": a.get("reasons") or [],
                                              "entity": grscicoll_entity(kind, a["entityMatched"]["key"], cache)})
        out[kind] = entry
    return out


def cmd_grscicoll(args):
    """Look institution and collection codes up in GRSciColl, the Global Registry of Scientific
    Collections, and print the candidates with all their identifiers. Only the distinct codes (and
    the country, if given) are sent; nothing is written."""
    queries = []
    if args.table:
        con = connect(args.db, read_only=True)
        t = next((n for n in (db_name(args.table), f"src_{args.table}") if n in db_tables(con)), None)
        if not t:
            sys.exit(f"No table {args.table} in the database. Run: dwcdp.py status")
        cols = [c for c in GRSCICOLL_COLUMNS if c in db_columns(con, t)]
        if not cols:
            sys.exit(f"{args.table} has none of the columns {', '.join(GRSCICOLL_COLUMNS)}.")
        sel = ", ".join(f"nullif(trim(CAST({q(c)} AS VARCHAR)), '') AS {q(c)}" for c in cols)
        for row in con.execute(f"SELECT {sel}, count(*) FROM {q(t)} GROUP BY ALL ORDER BY count(*) DESC").fetchall():
            query = {c: v for c, v in zip(cols, row) if v is not None}
            if query:
                queries.append((query, row[-1]))
    else:
        query = {c: getattr(args, c) for c in GRSCICOLL_COLUMNS if getattr(args, c)}
        if not query:
            sys.exit("Give a table, or at least one of --institutionCode, --collectionCode, --institutionID, --collectionID.")
        queries.append((query, None))
    cache, results = {}, []
    for query, rows in queries:
        params = {GRSCICOLL_COLUMNS[c]: v for c, v in query.items()}
        if args.country:
            params["country"] = args.country
        results.append({"query": query, "rows": rows, **grscicoll_lookup(params, cache)})
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    def entity_lines(e, indent):
        flag = "" if e["active"] in (True, None) else " (inactive)"
        lines = [f"{indent}{e['code']}: {e['name']}{flag}" + (f", {e['country']}" if e["country"] else "")]
        if e["institution"]:
            lines.append(f"{indent}  of institution: {e['institution']}")
        if e["alternativeCodes"]:
            lines.append(f"{indent}  other codes: {', '.join(e['alternativeCodes'])}")
        lines += [f"{indent}  {i['type']}: {i['identifier']}" for i in e["identifiers"]]
        return lines

    for r in results:
        q_text = ", ".join(f"{k} {v!r}" for k, v in r["query"].items()) + (f", country {args.country!r}" if args.country else "")
        print(f"{q_text}" + (f" ({r['rows']} rows)" if r["rows"] is not None else ""))
        for kind in ("institution", "collection"):
            m = r[kind]
            how = " ".join(x for x in [m["matchType"], m["status"]] if x) or "NONE"
            why = f" by {', '.join(m['reasons'])}" if m["reasons"] else ""
            print(f"  {kind}: {how}{why}")
            if m["match"]:
                print("\n".join(entity_lines(m["match"], "    ")))
            for a in m["alternatives"]:
                print(f"    or ({a['matchType']} by {', '.join(a['reasons'])}):")
                print("\n".join(entity_lines(a["entity"], "      ")))
        print()
    print("These are candidates from GRSciColl, not decisions. A match on a code alone is reported as "
          "DOUBTFUL. The data holder chooses which identifier, if any, goes in institutionID and collectionID.")


def cmd_status(args):
    con = connect(args.db, read_only=True)
    rows = []
    for t in db_tables(con):
        kind = "DwC-DP" if dwc_name(t) in schemas() else ("source" if t.startswith("src_") else "other")
        rows.append([t, kind, count(con, f"SELECT count(*) FROM {q(t)}")])
    print(table_text(rows, ["table", "kind", "rows"]) if rows else "The database is empty.")


# ---------------------------------------------------------------- checks

class Report:
    """Findings. `code` is the violation type GBIF's DwC-DP analyser (gbif/dwc-dp-analyser) reports
    for the same problem, at the same level; findings without one are this plugin's own checks."""

    def __init__(self):
        self.items = []

    def add(self, level, table, message, examples=None, field=None, code=None):
        self.items.append({"level": level, "table": table, "field": field, "message": message,
                           "examples": examples or [], "analyser": code})

    def error(self, *a, **k):
        self.add("error", *a, **k)

    def warning(self, *a, **k):
        self.add("warning", *a, **k)

    def info(self, *a, **k):
        self.add("info", *a, **k)

    @property
    def errors(self):
        return [i for i in self.items if i["level"] == "error"]

    def print(self, as_json=False, ok_text="No problems found.", analyser_summary=False):
        if as_json:
            print(json.dumps({"errors": len(self.errors), "items": self.items}, indent=2, default=str))
            return
        if not self.items:
            print(ok_text)
            return
        for level, title in (("error", "Must be fixed"), ("warning", "Worth checking"), ("info", "For information")):
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
        if analyser_summary:
            gbif = [i for i in self.errors if i["analyser"]]
            own = [i for i in self.errors if not i["analyser"]]
            if self.errors:
                print(f"GBIF's DwC-DP analyser would report {len(gbif)} of these {len(self.errors)} errors; "
                      f"{'the other' if len(own) == 1 else 'the other ' + str(len(own))} {'is' if len(own) == 1 else 'are'} this tool's own checks of DwC-DP rules." if own else
                      f"GBIF's DwC-DP analyser would report all {len(gbif)} errors.")
            else:
                print("No errors, so GBIF's DwC-DP analyser would find the package valid.")


def have(n, total=None):
    """'1 row has' / '3 rows have', or '1 of 4 rows has'."""
    noun = "row" if (total or n) == 1 else "rows"
    verb = "has" if n == 1 else "have"
    return f"{n} of {total} {noun} {verb}" if total is not None else f"{n} {noun} {verb}"


def examples(con, sql):
    return [r[0] for r in con.execute(f"{sql} LIMIT {EXAMPLES_SHOWN}").fetchall()]


def check_tables(con, present, report, descriptor_checked=False):
    """Relational and field checks. present: {dwc name: (db table, [columns], rows)}. With
    descriptor_checked, a required field that is absent was already reported by check_descriptor."""
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
                if c.get("required") and not descriptor_checked:
                    report.error(name, f"the required field {fname} is missing.", field=fname)
                continue
            F = q(fname)
            if c.get("required"):
                n = count(con, f"SELECT count(*) FROM {T} WHERE {F} IS NULL OR trim(CAST({F} AS VARCHAR)) = ''")
                if n:
                    pk = fname == s.get("primaryKey")
                    report.error(name, f"{have(n, rows)} no {fname}, which is required{' (the primary key)' if pk else ''}.", field=fname,
                                 code="PRIMARY_KEY_VIOLATION" if pk else None)
            if c.get("unique"):
                n = count(con, f"SELECT count(*) FROM (SELECT {F} FROM {T} WHERE {F} IS NOT NULL GROUP BY {F} HAVING count(*) > 1)")
                if n:
                    ex = examples(con, f"SELECT {F} FROM {T} WHERE {F} IS NOT NULL GROUP BY {F} HAVING count(*) > 1 ORDER BY 1")
                    what = "the primary key" if fname == s.get("primaryKey") else "a field that must be unique"
                    report.error(name, f"{n} {'value' if n == 1 else 'values'} of {fname} ({what}) {'occurs' if n == 1 else 'occur'} more than once.", ex, fname,
                                 code="PRIMARY_KEY_VIOLATION" if fname == s.get("primaryKey") else None)
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
                report.error(name, f"{have(n)} a value in {fname} that matches no {tfield} in {target} ({name} {pred} {target}).", examples(con, bad_sql + " ORDER BY 1"), fname,
                             code="FOREIGN_KEY_VIOLATION")

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

    check_identification_placement(con, present, report)


GENERIC_FIELDS = {"feedbackURL", "informationWithheld", "dataGeneralizations"}


def identification_fields(name):
    """The fields a material or occurrence shares with identification: its own copy of a name."""
    own = {f["name"] for f in schemas()[name]["fields"]}
    ident = {f["name"] for f in schemas()["identification"]["fields"]}
    return sorted(n for n in own & ident if n not in GENERIC_FIELDS and (not n.endswith(("_pk", "_fk")) or n == "identifiedBy_fk"))


def check_identification_placement(con, present, report):
    """Names belong in identification (the maintainers' rule, 2026-11-23): a material or occurrence
    that has an identification doesn't repeat it, and one with its own name fields is pointed to
    the identification table."""
    ident = present.get("identification")
    for name, link in (("material", "materialEntity_fk"), ("occurrence", "occurrence_fk")):
        if name not in present or not present[name][2]:
            continue
        table, cols, rows = present[name]
        fields = [f for f in identification_fields(name) if f in cols]
        if not fields:
            continue
        pk = schemas()[name]["primaryKey"]
        has_name = " OR ".join(f"{q(f)} IS NOT NULL" for f in fields)
        used = [f for f in fields if count(con, f"SELECT count(*) FROM {q(table)} WHERE {q(f)} IS NOT NULL")]
        if not used:
            continue
        if ident and ident[2] and link in ident[1]:
            n = count(con, f"SELECT count(*) FROM {q(table)} t WHERE ({has_name}) AND t.{q(pk)} IN (SELECT {q(link)} FROM {q(ident[0])} WHERE {q(link)} IS NOT NULL)")
            if n:
                report.warning(name, f"{have(n)} identification fields ({', '.join(used)}) and also an identification. "
                                     "Names belong in identification only; leave these fields empty.", field=used[0])
            rest = count(con, f"SELECT count(*) FROM {q(table)} t WHERE ({has_name}) AND t.{q(pk)} NOT IN (SELECT {q(link)} FROM {q(ident[0])} WHERE {q(link)} IS NOT NULL)")
            if rest:
                report.warning(name, f"{have(rest)} a name in its own fields ({', '.join(used)}) and no identification. "
                                     "The identification table is preferred for names.", field=used[0])
        else:
            report.warning(name, f"has names in its own fields ({', '.join(used)}). The identification table is preferred for "
                                 "names: an identification per name, and these fields left empty.", field=used[0])


def cmd_validate(args):
    con = connect(args.db, read_only=True)
    report = Report()
    present = {}
    for name, rows in dwc_tables_in(con).items():
        present[name] = (db_name(name), db_columns(con, db_name(name)), rows)
    if not present:
        sys.exit("The database has no DwC-DP tables yet. Start with: dwcdp.py init <tables>")
    check_tables(con, present, report)
    report.print(args.json, "No problems found in " + ", ".join(f"{t} ({r[2]} {'row' if r[2] == 1 else 'rows'})" for t, r in present.items()) + ".")
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


def summary_links(con, names, filled):
    """{table: [(field, predicate, target, linked rows)]} for the links in use between the tables."""
    links = {}
    for n in names:
        out = []
        for field, pred, target, _ in keys(schemas()[n], "foreignKeys"):
            if target in names and field in filled[n]:
                out.append((field, pred or field, target, filled[n][field]))
        links[n] = out
    return links


def summary_tree(names, rows, links):
    """The tables as a tree in plain text: each under the table its most used link points to, with
    the other links beside it. Reads as the ER diagram for a terminal."""
    parent = {}
    for n in names:
        out = [l for l in links[n] if l[2] != n]
        parent[n] = max(out, key=lambda l: l[3])[2] if out else None
    children = {n: [c for c in names if parent[c] == n] for n in names}
    lines = []

    def link_text(field, pred, target, linked, n):
        return f"{pred} {target} ({field}, {linked:,} of {rows[n]:,} rows)"

    def walk(n, prefix, last, depth):
        branch = "" if depth == 0 else ("└── " if last else "├── ")
        own = sorted((l for l in links[n] if l[2] == parent[n]), key=lambda l: -l[3])[:1]
        head = f"{n}  {rows[n]:,} row{'' if rows[n] == 1 else 's'}" + (f"  {link_text(*own[0], n)}" if own else "")
        lines.append(prefix + branch + head)
        inner = prefix + ("" if depth == 0 else ("    " if last else "│   "))
        for l in links[n]:
            if own and l is own[0]:
                continue
            mark = "↺ " if l[2] == n else "→ "
            lines.append(inner + ("│   " if children[n] else "    ") + mark + link_text(*l, n))
        for i, c in enumerate(children[n]):
            walk(c, inner, i == len(children[n]) - 1, depth + 1)

    for root in [n for n in names if parent[n] is None]:
        walk(root, "", True, 0)
        lines.append("")
    return lines


def column_blocks(header, rows, width):
    """Split a wide table into blocks of columns that fit the width, repeating the first column."""
    cells = [["" if v is None else str(v) for v in r] for r in rows]
    w = [min(max([len(h)] + [len(r[i]) for r in cells]), 40) for i, h in enumerate(header)]
    blocks, cur, used = [], [0], w[0]
    for i in range(1, len(header)):
        if used + 2 + w[i] > width and len(cur) > 1:
            blocks.append(cur)
            cur, used = [0], w[0]
        cur.append(i)
        used += 2 + w[i]
    blocks.append(cur)
    out = []
    for b in blocks:
        out.append(table_text([[r[i] for i in b] for r in cells], [header[i] for i in b], last=40)
                   .replace("\n", "\n  ").join(["  ", ""]))
    return "\n\n".join(out)


def cmd_summary(args):
    """What the working database holds: the tables and their rows, how they link, and the first
    rows of each, with only the columns that have values."""
    con = connect(args.db, read_only=True)
    present = {t: n for t, n in dwc_tables_in(con).items() if n}
    if not present:
        sys.exit("No DwC-DP table has rows yet. Run: dwcdp.py status")
    ordered, cycle = fill_order(list(present))
    names = ordered + cycle
    filled = {}
    for n in names:
        cols = [c for c in db_columns(con, db_name(n)) if c in field_map(schema(n))]
        counts = con.execute("SELECT " + ", ".join(f"count({q(c)})" for c in cols) + f" FROM {q(db_name(n))}").fetchone()
        filled[n] = {c: k for c, k in zip(cols, counts) if k}
    width = args.width or shutil.get_terminal_size((120, 40)).columns

    print(f"DwC-DP tables in {args.db}: {len(names)}, {sum(present.values()):,} rows in all\n")
    print(table_text([[n, f"{present[n]:,}", schema(n).get("description", "")] for n in names],
                     ["table", "rows", "what one row is"], last=90))
    print("\nHow the tables link (each table under the one it points to; → another link, ↺ a link within the table):\n")
    print("\n".join(summary_tree(names, present, summary_links(con, names, filled))).rstrip())
    print("\nFor a drawn diagram: dwcdp.py diagram gives Mermaid text, which GitHub and other Mermaid viewers draw.")
    if args.rows:
        print(f"\n{args.rows} rows of each table, those with the most values filled in, and only the "
              "columns that have values somewhere in the table:")
        for n in names:
            cols = [c for c in db_columns(con, db_name(n)) if c in filled[n]]
            fullness = " + ".join(f"({q(c)} IS NOT NULL)::INT" for c in cols)
            cur = con.execute(f"SELECT {', '.join(q(c) for c in cols)} FROM {q(db_name(n))} "
                              f"ORDER BY {fullness} DESC, {q(cols[0])} LIMIT {int(args.rows)}")
            print(f"\n{n} ({present[n]:,} rows)")
            print(column_blocks(cols, cur.fetchall(), width - 2))
    print("\nAsk Claude anything about these tables, in your own words: Claude answers by querying the "
          f"working database ({args.db}) with DuckDB. For example:")
    examples = ["How many records per year?"] if "event" in present else []
    if "identification" in present:
        examples.append("Which ten names occur most often?")
    if "organism-interaction" in present:
        examples.append("Which interaction types are there, and between which taxa?")
    if "material" in present:
        examples.append("How many specimens are in each collection?")
    if "media" in present:
        examples.append("Which records have the most images?")
    examples.append("Show me everything linked to one record.")
    print("\n".join(f"  - {e}" for e in examples[:4]))


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


# ---------------------------------------------------------------- metadata

LICENSES = {
    "CC0-1.0": ("https://creativecommons.org/publicdomain/zero/1.0/legalcode", "Creative Commons Zero v1.0 Universal"),
    "CC-BY-4.0": ("https://creativecommons.org/licenses/by/4.0/legalcode", "Creative Commons Attribution 4.0 International"),
    "CC-BY-NC-4.0": ("https://creativecommons.org/licenses/by-nc/4.0/legalcode", "Creative Commons Attribution Non Commercial 4.0 International"),
}

METADATA_TEMPLATE = {
    "title": "",
    "description": "",
    "license": "one of CC0-1.0, CC-BY-4.0, CC-BY-NC-4.0, or {\"name\": \"...\", \"path\": \"https://...\", \"title\": \"...\"}",
    "creators": [{"givenName": "", "surName": "", "organization": "", "email": "", "orcid": ""}],
    "contacts": [{"givenName": "", "surName": "", "organization": "", "email": "", "orcid": ""}],
    "metadataProviders": [],
    "keywords": [],
    "language": "",
    "homepage": "",
    "methods": [],
    "coverage": {"geographicDescription": ""},
}


def read_metadata(path):
    with open(path, encoding="utf-8") as fh:
        try:
            md = json.load(fh)
        except ValueError as e:
            sys.exit(f"{path} is not valid JSON: {e}")
    problems = []
    if not (md.get("title") or "").strip():
        problems.append("title is missing")
    for role in ("creators", "contacts"):
        people = [p for p in md.get(role) or [] if any((p.get(k) or "").strip() for k in ("surName", "organization"))]
        if not people:
            problems.append(f"{role} needs at least one person (with surName) or organization")
        md[role] = people
    md["metadataProviders"] = [p for p in md.get("metadataProviders") or [] if any((p.get(k) or "").strip() for k in ("surName", "organization"))]
    lic = md.get("license")
    if isinstance(lic, str) and lic not in LICENSES:
        problems.append(f"license {lic!r} is not one of {', '.join(LICENSES)}; give another as {{\"name\", \"path\", \"title\"}}")
    if problems:
        sys.exit(f"{path}: " + "; ".join(problems) + ". Fill it in with the data holder (references/package.md).")
    return md


def license_of(md):
    lic = md.get("license")
    if not lic:
        return None
    if isinstance(lic, str):
        url, title = LICENSES[lic]
        return {"name": lic, "path": url, "title": title}
    return {k: lic[k] for k in ("name", "path", "title") if lic.get(k)}


def person_name(p):
    return " ".join(x for x in ((p.get("givenName") or "").strip(), (p.get("surName") or "").strip()) if x) or (p.get("organization") or "").strip()


def derived_coverage(con, present):
    """Bounding box and date range of the package's events, from decimalLatitude/Longitude and the
    ISO dates in eventDate."""
    if "event" not in present:
        return {}
    table, cols, _ = present["event"]
    cov = {}
    if "decimalLatitude" in cols and "decimalLongitude" in cols:
        box = con.execute(f"SELECT min(decimalLatitude), max(decimalLatitude), min(decimalLongitude), max(decimalLongitude) FROM {q(table)}").fetchone()
        if box[0] is not None:
            cov.update(south=box[0], north=box[1], west=box[2], east=box[3])
    if "eventDate" in cols:
        dates = [d for (v,) in con.execute(f"SELECT eventDate FROM {q(table)} WHERE eventDate IS NOT NULL").fetchall()
                 for d in re.findall(r"\d{4}-\d{2}-\d{2}", str(v))]
        if dates:
            cov.update(begin=min(dates), end=max(dates))
    return cov


def eml_xml(md, cov, package_id):
    """EML 2.2.0, with dataset elements in the order the schema requires."""
    import xml.etree.ElementTree as ET
    ns = "https://eml.ecoinformatics.org/eml-2.2.0"
    ET.register_namespace("eml", ns)
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root = ET.Element(f"{{{ns}}}eml", {
        "packageId": package_id, "system": "dwc-dp-claude-plugin", "scope": "system",
        "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": f"{ns} https://eml.ecoinformatics.org/eml-2.2.0/eml.xsd"})
    ds = ET.SubElement(root, "dataset")

    def sub(parent, tag, text=None, **attrs):
        e = ET.SubElement(parent, tag, attrs)
        if text is not None:
            e.text = text
        return e

    def party(tag, p):
        e = sub(ds, tag)
        if (p.get("surName") or "").strip():
            n = sub(e, "individualName")
            if (p.get("givenName") or "").strip():
                sub(n, "givenName", p["givenName"].strip())
            sub(n, "surName", p["surName"].strip())
        if (p.get("organization") or "").strip():
            sub(e, "organizationName", p["organization"].strip())
        if (p.get("email") or "").strip():
            sub(e, "electronicMailAddress", p["email"].strip())
        if (p.get("orcid") or "").strip():
            sub(e, "userId", p["orcid"].strip(), directory="https://orcid.org/")

    if md.get("id"):
        sub(ds, "alternateIdentifier", md["id"])
    sub(ds, "title", md["title"].strip())
    for p in md["creators"]:
        party("creator", p)
    for p in md["metadataProviders"]:
        party("metadataProvider", p)
    sub(ds, "pubDate", datetime.date.today().isoformat())
    if (md.get("language") or "").strip():
        sub(ds, "language", md["language"].strip())
    if (md.get("description") or "").strip():
        a = sub(ds, "abstract")
        for para in [x for x in md["description"].split("\n\n") if x.strip()]:
            sub(a, "para", para.strip())
    if md.get("keywords"):
        k = sub(ds, "keywordSet")
        for w in md["keywords"]:
            sub(k, "keyword", w)
        sub(k, "keywordThesaurus", "N/A")
    lic = license_of(md)
    if lic:
        r = sub(ds, "intellectualRights")
        para = sub(r, "para", "This work is licensed under a ")
        link = sub(para, "ulink", url=lic.get("path", ""))
        sub(link, "citetitle", lic.get("title") or lic.get("name"))
        link.tail = "."
        ld = sub(ds, "licensed")
        sub(ld, "licenseName", lic.get("title") or lic.get("name"))
        if lic.get("path"):
            sub(ld, "url", lic["path"])
        if lic.get("name"):
            sub(ld, "identifier", lic["name"])
    geo_desc = ((md.get("coverage") or {}).get("geographicDescription") or "").strip()
    if (geo_desc and "north" in cov) or "begin" in cov:
        c = sub(ds, "coverage")
        if geo_desc and "north" in cov:
            g = sub(c, "geographicCoverage")
            sub(g, "geographicDescription", geo_desc)
            b = sub(g, "boundingCoordinates")
            for side in ("west", "east", "north", "south"):
                sub(b, f"{side}BoundingCoordinate", str(cov[side]))
        if "begin" in cov:
            t = sub(c, "temporalCoverage")
            rd = sub(t, "rangeOfDates")
            sub(sub(rd, "beginDate"), "calendarDate", cov["begin"])
            sub(sub(rd, "endDate"), "calendarDate", cov["end"])
    for p in md["contacts"]:
        party("contact", p)
    if md.get("methods"):
        m = sub(ds, "methods")
        for step in md["methods"]:
            sub(sub(sub(m, "methodStep"), "description"), "para", step)
    if hasattr(ET, "indent"):
        ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def descriptor_metadata(md):
    """Package-level properties of the Data Package specification (v1)."""
    out = {}
    if (md.get("description") or "").strip():
        out["description"] = md["description"].strip()
    lic = license_of(md)
    if lic:
        out["licenses"] = [lic]
    contributors = []
    for role, people in (("author", md["creators"]), ("maintainer", md["contacts"])):
        for p in people:
            c = {"title": person_name(p), "role": role}
            if (p.get("email") or "").strip():
                c["email"] = p["email"].strip()
            if (p.get("orcid") or "").strip():
                c["path"] = p["orcid"].strip() if p["orcid"].startswith("http") else "https://orcid.org/" + p["orcid"].strip()
            if (p.get("organization") or "").strip() and (p.get("surName") or "").strip():
                c["organization"] = p["organization"].strip()
            contributors.append(c)
    out["contributors"] = contributors
    if md.get("keywords"):
        out["keywords"] = md["keywords"]
    if (md.get("homepage") or "").strip():
        out["homepage"] = md["homepage"].strip()
    return out


def cmd_metadata_template(args):
    if os.path.exists(args.file):
        sys.exit(f"{args.file} exists; edit it, or choose another name.")
    with open(args.file, "w", encoding="utf-8") as fh:
        json.dump(METADATA_TEMPLATE, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {args.file}. Fill it in with the data holder, then: dwcdp.py package <folder> --metadata {args.file}")


def cmd_package(args):
    con = connect(args.db, read_only=True)
    present = {n: (db_name(n), db_columns(con, db_name(n)), r) for n, r in dwc_tables_in(con).items() if r}
    if not present:
        sys.exit("There are no DwC-DP rows to package yet.")
    report = Report()
    check_tables(con, present, report)
    if not args.name:
        report.warning("datapackage.json", "will have no name, a short identifier the Data Package specification recommends. Add --name.", code="MISSING_NAME")
    if report.errors:
        report.print()
        sys.exit("Not packaged: fix the problems above first (dwcdp.py validate shows them again).")
    md = read_metadata(args.metadata) if args.metadata else None
    if args.name and not NAME_PATTERN.match(args.name):
        sys.exit(f"--name {args.name!r} may only have lower-case letters, digits and - . _ /, for example 'beetles-mols-2024'.")
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
        # A whole number in a number field is written without ".0", as the data holder wrote it.
        number = lambda c: fm[c]["type"] == "number"
        select = ", ".join(
            f"CASE WHEN {q(c)} = trunc({q(c)}) AND abs({q(c)}) < 1e15 THEN CAST(CAST({q(c)} AS BIGINT) AS VARCHAR) ELSE CAST({q(c)} AS VARCHAR) END AS {q(c)}"
            if number(c) else q(c) for c in used)
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
        print(f"{path}: {rows} {'row' if rows == 1 else 'rows'}, {len(used)} fields")
    descriptor = {"profile": PROFILE_URL}
    if md:
        for key in ("id", "title", "version"):
            if md.get(key) and not getattr(args, key):
                setattr(args, key, md[key])
    for key in ("name", "id", "title", "version"):
        if getattr(args, key):
            descriptor[key] = getattr(args, key)
    if md:
        descriptor.update(descriptor_metadata(md))
    descriptor["created"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    descriptor["resources"] = resources
    with open(os.path.join(out, "datapackage.json"), "w", encoding="utf-8") as fh:
        json.dump(descriptor, fh, indent=2, ensure_ascii=False)
    if args.eml:
        shutil.copyfile(args.eml, os.path.join(out, "eml.xml"))
    elif md:
        cov = derived_coverage(con, present)
        with open(os.path.join(out, "eml.xml"), "w", encoding="utf-8") as fh:
            fh.write(eml_xml(md, cov, args.id or args.name or os.path.basename(out)))
        if cov:
            print("Coverage from the events: " + ", ".join(f"{k} {v}" for k, v in cov.items())
                  + ". Show it to the data holder.")
        if "north" in cov and not ((md.get("coverage") or {}).get("geographicDescription") or "").strip():
            print("No geographic coverage in eml.xml: EML needs a geographicDescription with the bounding box (coverage.geographicDescription).")
        for missing in [k for k in ("description", "license") if not md.get(k)]:
            print(f"Note: metadata.json has no {missing}.")
    print(f"\nWrote {args.out}: datapackage.json{', eml.xml' if args.eml or md else ''} and {len(resources)} tables.")
    print("dwcdp.py summary shows what the tables hold: rows, links and examples.")
    for w in report.items:
        print(f"  note, {w['table']}: {w['message']}")


# Field types of the Table Schema specification, and the DuckDB types GBIF's DwC-DP analyser
# casts them to (FrictionlessDescriptorValidator and DuckDbDataTypeValidator in gbif/dwc-dp-analyser).
FRICTIONLESS_TYPES = {"string", "number", "integer", "boolean", "object", "array", "date", "time",
                      "datetime", "year", "yearmonth", "duration", "geopoint", "geojson", "any"}
CAST_TYPES = {"integer": "BIGINT", "number": "DOUBLE", "boolean": "BOOLEAN", "date": "DATE",
              "datetime": "TIMESTAMP", "time": "TIME", "year": "INTEGER", "object": "JSON", "array": "JSON"}
# The field descriptor properties the analyser compares with the canonical schema: always, and
# only when the package declares them (DwcDpTableSchemaValidator).
DESCRIPTOR_REQUIRED = ("type", "title", "description", "dcterms:isVersionOf")
DESCRIPTOR_OPTIONAL = ("format", "namespace", "dcterms:references")
NAME_PATTERN = re.compile(r"^([-a-z0-9._/])+$")
# A resource path in the Data Package specification's schema: relative, not starting with . / or ~,
# and without "..".
PATH_PATTERN = re.compile(r"^(?=^[^./~])(^((?!\.{2}).)*$).*$")


def key_refs(schema_node, name):
    """{(fields, predicate, target resource, target fields)} of foreignKeys and weakForeignKeys,
    compared as the analyser does (ForeignKeyCrossChecker): predicate included, an empty target
    resource meaning the table itself."""
    out = set()
    for kind in ("foreignKeys", "weakForeignKeys"):
        for k in schema_node.get(kind) or []:
            fields = tuple(x.strip() for x in as_list(k.get("fields")) if x and x.strip())
            if not fields:
                continue
            ref = k.get("reference") or {}
            out.add((fields, (k.get("predicate") or "").strip(), (ref.get("resource") or "").strip(),
                     tuple(x.strip() for x in as_list(ref.get("fields")) if x and x.strip())))
    return out


def describe_ref(ref):
    fields, pred, target, tfields = ref
    return f"{'+'.join(fields)} → {target or 'itself'}.{'+'.join(tfields)}" + (f" ({pred})" if pred else "")


def check_descriptor(dp, root, report):
    """The descriptor checks of GBIF's DwC-DP analyser, at its default severities, plus the guide's
    rules it doesn't check (marked as this tool's own by having no code)."""
    profile = dp.get("profile") or ""
    # The analyser runs its profile and table schema checks (layers 1 and 2) only for a profile it
    # recognises; otherwise it reports UNRECOGNIZED_PROFILE_VERSION and skips them. Findings of those
    # layers then count as this tool's own.
    recognised = bool(re.match(r"^https?://rs\.tdwg\.org/dwc-dp/[^/]+/dwc-dp-profile\.json$", profile))
    layer2 = lambda code: code if recognised else None
    if not recognised:
        report.error("datapackage.json", f"profile is {profile!r}; a DwC-DP names a versioned profile on rs.tdwg.org, such as {PROFILE_URL}.",
                     code="UNRECOGNIZED_PROFILE_VERSION")
    elif f"/dwc-dp/{VERSION}/" not in profile:
        report.error("datapackage.json", f"profile is {profile}, and this tool checks DwC-DP {VERSION}.")
    if not (dp.get("name") or "").strip():
        report.warning("datapackage.json", "has no name, a short identifier for the package that the Data Package specification recommends (package --name).",
                       code="MISSING_NAME")
    elif not NAME_PATTERN.match(dp["name"]):
        report.warning("datapackage.json", f"name {dp['name']!r} may only have lower-case letters, digits and - . _ /.", code=layer2("JSON_SCHEMA_VIOLATION"))
    resources = dp.get("resources")
    if not isinstance(resources, list) or not resources:
        report.error("datapackage.json", "has no resources.", code="MISSING_RESOURCES")
        return []
    declared_fields = {}
    for r in resources:
        rname = (r.get("name") or "").strip()
        if rname:
            declared_fields[rname] = {(f.get("name") or "").strip() for f in ((r.get("schema") or {}).get("fields") or []) if isinstance(f, dict)}
    usable = []
    for i, r in enumerate(resources):
        name = (r.get("name") or "").strip()
        label = name or f"resource {i + 1}"
        if not name:
            report.warning(label, "has no name.", code="RESOURCE_MISSING_NAME")
        rel = r.get("path") or ""
        if isinstance(rel, str) and rel and not PATH_PATTERN.match(rel):
            report.warning(label, f"path {rel!r} is not a path the Data Package specification allows (relative, not starting with . / or ~, without ..).", code=layer2("JSON_SCHEMA_VIOLATION"))
        path = os.path.realpath(os.path.join(root, rel)) if isinstance(rel, str) and rel else None
        if not path:
            report.error(label, "has no path to its file.", code="PATH_NOT_FOUND")
        elif os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
            report.error(label, f"path {rel!r} points outside the package.", code="PATH_NOT_FOUND")
            path = None
        elif not os.path.exists(path):
            report.error(label, f"its file {rel!r} is not in the package.", code="PATH_NOT_FOUND")
            path = None
        rs = r.get("schema")
        fields = [f for f in ((rs or {}).get("fields") or []) if isinstance(f, dict)] if isinstance(rs, dict) else []
        for f in fields:
            t = f.get("type")
            if t is not None and t not in FRICTIONLESS_TYPES:
                report.warning(label, f"field {f.get('name')} has type {t!r}, which the Table Schema specification doesn't have.", field=f.get("name"), code="UNKNOWN_FIELD_TYPE")
        for k in (rs or {}).get("foreignKeys") or [] if isinstance(rs, dict) else []:
            target = ((k.get("reference") or {}).get("resource") or "").strip()
            if target and target not in declared_fields:
                report.warning(label, f"declares a foreign key to {target!r}, which is not in the package.", code="FK_UNKNOWN_REFERENCE_RESOURCE")
        if name not in schemas():
            if r.get("profile") == "tabular-data-resource":
                report.info(label, f"is not a DwC-DP {VERSION} table, so only its file was checked.")
            continue
        s = schemas()[name]
        fm = field_map(s)
        if r.get("profile") != "tabular-data-resource":
            report.warning(name, "resource profile must be tabular-data-resource.", code=layer2("JSON_SCHEMA_VIOLATION"))
        if r.get("mediatype") != "text/csv":
            report.error(name, f"mediatype is {r.get('mediatype')!r}; the DwC-DP guide (3.2.2) requires text/csv.")
        if not isinstance(rs, dict):
            report.error(name, "schema must be the table schema itself, not a reference to one (DwC-DP guide 3.2.2).")
            continue
        names = [(f.get("name") or "").strip() for f in fields]
        dupes = sorted({n for n in names if n and names.count(n) > 1})
        if dupes:
            report.error(name, f"{len(dupes)} {'field is' if len(dupes) == 1 else 'fields are'} declared more than once.", dupes, code=layer2("FIELD_DUPLICATE"))
        missing_props = [f"{f.get('name')}: {p}" for f in fields for p in ("name", "title", "description", "type", "dcterms:isVersionOf") if f.get(p) in (None, "")]
        if missing_props:
            report.warning(name, f"{len(missing_props)} field {'descriptor lacks' if len(missing_props) == 1 else 'descriptors lack'} a property the DwC-DP profile requires.", missing_props, code=layer2("JSON_SCHEMA_VIOLATION"))
        bad_iri = [f["name"] for f in fields if f.get("dcterms:isVersionOf") and not re.match(r"^https?://.+$", str(f["dcterms:isVersionOf"]))]
        if bad_iri:
            report.warning(name, "dcterms:isVersionOf must be a URL.", bad_iri, code=layer2("JSON_SCHEMA_VIOLATION"))
        required_missing = [f["name"] for f in s["fields"] if constraints(f).get("required") and f["name"] not in names]
        if required_missing:
            report.error(name, f"{len(required_missing)} required {'field is' if len(required_missing) == 1 else 'fields are'} not declared.", required_missing, code=layer2("REQUIRED_FIELD_MISSING"))
        unknown = [n for n in names if n and n not in fm]
        if unknown:
            report.info(name, f"{len(unknown)} of its {len(fields)} fields {'is not a DwC-DP ' + VERSION + ' field' if len(unknown) == 1 else 'are not DwC-DP ' + VERSION + ' fields'} of {name} (custom fields SHOULD NOT be added, DwC-DP guide 3.3).", unknown, code=layer2("UNKNOWN_FIELD"))
        absent, differ = {}, {}
        for f in fields:
            v = fm.get((f.get("name") or "").strip())
            if not v:
                continue
            for prop in DESCRIPTOR_REQUIRED:
                if f.get(prop) is None:
                    absent.setdefault(prop, []).append(v["name"])
                elif str(f.get(prop)).strip() != str(v.get(prop) or "").strip():
                    differ.setdefault(prop, []).append(v["name"])
            for prop in DESCRIPTOR_OPTIONAL:
                if prop in f and str(f.get(prop)).strip() != str(v.get(prop) or "").strip():
                    differ.setdefault(prop, []).append(v["name"])
        for prop, lst in absent.items():
            report.error(name, f"{len(lst)} {'field lacks' if len(lst) == 1 else 'fields lack'} {prop}.", lst, code=layer2("FIELD_DEFINITION_MISSING"))
        for prop, lst in differ.items():
            code = layer2("FIELD_TYPE_MISMATCH" if prop == "type" else "FIELD_DEFINITION_MISMATCH")
            report.warning(name, f"{len(lst)} {'field has' if len(lst) == 1 else 'fields have'} a {prop} other than the DwC-DP schema's (copy field descriptors from it, DwC-DP guide 3.3).", lst, code=code)
        pk = rs.get("primaryKey")
        if pk is not None and as_list(pk) != as_list(s.get("primaryKey")):
            report.error(name, f"primaryKey is {pk!r}; the DwC-DP schema defines {s.get('primaryKey')!r} (DwC-DP guide 3.3).")
        canonical, declared = key_refs(s, name), key_refs(rs, name)
        present_names = set(names)
        undeclared = [describe_ref(k) for k in canonical if set(k[0]) <= present_names and k not in declared]
        if undeclared:
            report.warning(name, f"has the {'field' if len(undeclared) == 1 else 'fields'} of {len(undeclared)} {'relationship' if len(undeclared) == 1 else 'relationships'} in the DwC-DP schema without declaring {'it' if len(undeclared) == 1 else 'them'}.", sorted(undeclared), code=layer2("FOREIGN_KEY_MISSING"))
        for k in sorted(declared):
            fields_, _, target, tfields = k
            for fld in fields_:
                if fld not in present_names:
                    report.warning(name, f"declares {describe_ref(k)}, and has no field {fld}.", code=layer2("FOREIGN_KEY_FIELD_NOT_DECLARED"))
            tgt = target or name
            if tgt in declared_fields:
                for tf in tfields:
                    if tf not in declared_fields[tgt]:
                        report.warning(name, f"declares {describe_ref(k)}, and {tgt} has no field {tf}.", code=layer2("FOREIGN_KEY_TARGET_FIELD_NOT_DECLARED"))
            elif any(rk == k for rk in key_refs({"weakForeignKeys": rs.get("weakForeignKeys") or []}, name)):
                report.warning(name, f"refers by identifier to {tgt} ({describe_ref(k)}), and the package has no {tgt} table. That is expected when the identifiers point outside the package.", code=layer2("FK_UNKNOWN_REFERENCE_RESOURCE"))
        not_canonical = [describe_ref(k) for k in declared if k not in canonical]
        if not_canonical:
            report.warning(name, f"{len(not_canonical)} declared {'relationship is not one' if len(not_canonical) == 1 else 'relationships are not ones'} the DwC-DP schema defines.", sorted(not_canonical), code=layer2("FOREIGN_KEY_NOT_IN_CANONICAL_SCHEMA"))
        if path:
            usable.append((r, name, fields, path))
    return usable


def check_eml(root, report):
    """The EML checks of GBIF's DwC-DP analyser that need no XSD: well-formed, title and creator.
    They don't affect its verdict, so they are warnings here."""
    path = os.path.join(root, "eml.xml")
    if not os.path.exists(path):
        return
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(path).getroot()
    except ET.ParseError as e:
        report.warning("eml.xml", f"is not well-formed XML ({e}). GBIF's analyser reports this as an error, though it doesn't make the package invalid.", code="INVALID_XML")
        return
    local = lambda el: el.tag.rsplit("}", 1)[-1]
    found = {local(el): el for el in tree.iter() if local(el) in ("title", "creator")}
    if "title" not in found or not "".join(found["title"].itertext()).strip():
        report.warning("eml.xml", "has no title.", code="EML_MISSING_TITLE")
    if "creator" not in found or not "".join(found["creator"].itertext()).strip():
        report.warning("eml.xml", "has no creator.", code="EML_MISSING_CREATOR")
    report.info("eml.xml", "was not checked against the EML 2.2.0 schema; GBIF's analyser does that.")


def cmd_check(args):
    root = os.path.abspath(args.path)
    dp_path = os.path.join(root, "datapackage.json")
    if not os.path.exists(dp_path):
        sys.exit(f"No datapackage.json in {args.path}")
    report = Report()
    try:
        with open(dp_path, encoding="utf-8") as fh:
            dp = json.load(fh)
    except ValueError as e:
        report.error("datapackage.json", f"is not valid JSON ({e}).", code="INVALID_JSON")
        report.print(args.json, analyser_summary=True)
        sys.exit(1)
    usable = check_descriptor(dp, root, report)
    check_eml(root, report)
    con = connect(":memory:")
    present = {}
    for r, name, fields, path in usable:
        names = [(f.get("name") or "").strip() for f in fields]
        if len(set(names)) != len(names):
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
            report.error(name, f"the file's columns do not match the schema's fields in order and number (file: {len(cols)}, schema: {len(names)}; DwC-DP guide 3.3).", [c for c in cols if c not in names][:EXAMPLES_SHOWN] or None)
            continue
        con.execute(f"UPDATE {q(table)} SET " + ", ".join(f"{q(c)} = NULLIF({q(c)}, '')" for c in cols))
        rows = count(con, f"SELECT count(*) FROM {q(table)}")
        # Types are checked against the type the package declares, as the analyser does.
        for f in fields:
            cast = CAST_TYPES.get(str(f.get("type", "")).lower())
            if not cast:
                continue
            F = q(f["name"])
            bad = f"FROM {q(table)} WHERE {F} IS NOT NULL AND TRY_CAST({F} AS {cast}) IS NULL"
            n = count(con, f"SELECT count(*) {bad}")
            if n:
                report.error(name, f"{n} {'value' if n == 1 else 'values'} of {f['name']} {'is' if n == 1 else 'are'} not of type {f['type']}.", examples(con, f"SELECT DISTINCT {F} {bad}"), f["name"], code="DATA_TYPE_VIOLATION")
        present[name] = (table, cols, rows)
    check_tables(con, present, report, descriptor_checked=True)
    report.print(args.json, f"No problems found in {args.path}: " + ", ".join(f"{t} ({r[2]} {'row' if r[2] == 1 else 'rows'})" for t, r in present.items()) + ".", analyser_summary=True)
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
    s = sub.add_parser("suggest", help="for each column of a source table: matching DwC-DP fields, an interaction or an assertion candidate")
    s.add_argument("source", help="a source table, e.g. src_samples or samples")
    s.add_argument("--table", help="only fields of this DwC-DP table, e.g. event")
    s.set_defaults(func=cmd_suggest)
    s = sub.add_parser("grscicoll", help="look institution and collection codes up in GRSciColl (sends only the codes, over the internet)")
    s.add_argument("table", nargs="?", help="a table with institutionCode, collectionCode, institutionID or collectionID columns, e.g. material")
    for c in GRSCICOLL_COLUMNS:
        s.add_argument(f"--{c}", dest=c)
    s.add_argument("--country", help="ISO 3166-1 alpha-2 code, to narrow the match, e.g. DK")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_grscicoll)
    s = sub.add_parser("summary", help="the tables made, their rows, how they link, and their first rows")
    s.add_argument("--rows", type=int, default=3, help="rows to show per table (0 for none)")
    s.add_argument("--width", type=int, help="line width for the example rows (default: the terminal's)")
    s.set_defaults(func=cmd_summary)
    s = sub.add_parser("validate", help="check the DwC-DP tables in the database")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_validate)
    s = sub.add_parser("diagram", help="Mermaid diagram of the tables in use")
    s.add_argument("tables", nargs="*")
    s.add_argument("--all", action="store_true", help="include empty tables")
    s.set_defaults(func=cmd_diagram)
    s = sub.add_parser("package", help="write the tables and datapackage.json to a folder")
    s.add_argument("out")
    s.add_argument("--name", help="a short identifier for the package: lower-case letters, digits, - . _ /")
    s.add_argument("--metadata", help="metadata.json: written as eml.xml and as datapackage.json properties")
    s.add_argument("--eml", help="an existing eml.xml to include as it is (instead of writing one from --metadata)")
    s.add_argument("--id", help="dataset identifier, preferably a DOI")
    s.add_argument("--title")
    s.add_argument("--version", help="dataset version")
    s.add_argument("--overwrite", action="store_true")
    s.set_defaults(func=cmd_package)
    s = sub.add_parser("metadata-template", help="write an empty metadata.json to fill in")
    s.add_argument("file", nargs="?", default="metadata.json")
    s.set_defaults(func=cmd_metadata_template)
    s = sub.add_parser("check", help="check a DwC-DP package on disk")
    s.add_argument("path")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
