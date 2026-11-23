# GBIF DwC-DP analyser reports

`reports.txt` is the text output of `dwc-dp-analyser` 0.0.16 (gbif/dwc-dp-analyser, jar with
SHA-256 `5b3dbb518cdeec7cb7fbf48859f70084c457cc444f22687b8994160370965e19`), run with
`--report VERIFY` on 2026-11-23 by the maintainer. Its input was the 18 packages that
`tests/analyser_packages.py` builds: a good one, and 17 copies with one thing broken each. The timestamped log lines and durations are
left out.

To record again, for example with a new analyser release:

    python3 tests/analyser_packages.py /tmp/packages
    cd /tmp/packages && for d in */; do d=${d%/}; echo "== $d"; dwc-dp-analyser $d/datapackage.json --report VERIFY 2>&1 | grep -v "DwcDpProfileRegistry\|^Duration\|WARN  o.g"; echo "exit $?"; done

and replace `reports.txt` with the output. `AnalyserReports` compares `check` with every package in it.
