#!/usr/bin/env python3
"""Copy the DwC-DP table schemas, profile and term lists from a pinned tdwg/dwc commit.

    python3 tools/pin_schemas.py <commit sha>

Replaces skills/dwc-dp/schemas/<version>/ with the files at that commit and rewrites
PINNED_VERSION.md. The vendored files are never edited by hand; rerun this with a new pin.
"""
import json
import os
import shutil
import sys
import urllib.request

REPO = "tdwg/dwc"
FILES = [
    "dwc-dp/dwc-dp-profile.json",
    "build/dwc-dp/dwc-dp-tables.csv",
    "build/dwc-dp/dwc-dp-fields.csv",
]
SCHEMA_DIR = "dwc-dp/table-schemas"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "dwc-dp", "schemas")


def get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": "dwc-dp-claude-plugin", **({"Accept": accept} if accept else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 40:
        sys.exit("usage: pin_schemas.py <full 40-character commit sha of tdwg/dwc>")
    sha = sys.argv[1]
    commit = json.loads(get(f"https://api.github.com/repos/{REPO}/commits/{sha}"))
    date = commit["commit"]["committer"]["date"][:10]
    message = commit["commit"]["message"].split("\n")[0]
    listing = json.loads(get(f"https://api.github.com/repos/{REPO}/contents/{SCHEMA_DIR}?ref={sha}"))
    names = sorted(e["name"] for e in listing if e["name"].endswith(".json"))
    raw = lambda path: get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{path}")

    profile = json.loads(raw(FILES[0]))
    version = profile["version"].rstrip("/").split("/")[-1]
    target = os.path.join(ROOT, version)
    tmp = target + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.join(tmp, "table-schemas"))
    for path in FILES:
        with open(os.path.join(tmp, os.path.basename(path)), "wb") as f:
            f.write(raw(path))
    for name in names:
        with open(os.path.join(tmp, "table-schemas", name), "wb") as f:
            f.write(raw(f"{SCHEMA_DIR}/{name}"))
    with open(os.path.join(tmp, "PINNED_VERSION.md"), "w") as f:
        f.write(f"""# DwC-DP {version} — pinned source

Copied verbatim by `tools/pin_schemas.py`. Do not edit these files; rerun the script with a new pin.

- **Source:** https://github.com/{REPO} (licence CC-BY-4.0)
- **Pinned commit:** `{sha}` ({date}, "{message}")
- **Profile:** `{profile['version']}`
- **Files:** `{FILES[0]}`, `{FILES[1]}`, `{FILES[2]}`, and the {len(names)} files in `{SCHEMA_DIR}/`
""")
    shutil.rmtree(target, ignore_errors=True)
    os.rename(tmp, target)
    print(f"Pinned DwC-DP {version} from {REPO}@{sha[:10]} ({date}): {len(names)} table schemas in {os.path.relpath(target)}")


if __name__ == "__main__":
    main()
