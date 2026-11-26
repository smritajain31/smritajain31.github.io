#!/usr/bin/env python3
"""Weekly link check for the archive.

Writes data/link-status.json: {url: {"status": ok|dead|unknown, "code", "checked", "fails"}}.
A link is only marked "dead" after two checks in a row return 404/410 or the
host no longer resolves, so a one-off outage never hides an entry.
Sites that block robots (401/403/429/5xx, timeouts) are recorded as "unknown".
"""
import datetime as dt
import json
import socket
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "archive.json"
OUT = ROOT / "data" / "link-status.json"
UA = "Mozilla/5.0 (compatible; SJ-archive-linkcheck/1.0; +https://smritajain31.github.io/archive/)"


def probe(url):
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return "ok", r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 400, 404, 501):
                continue  # many servers reject HEAD; retry with GET
            if e.code in (404, 410):
                return "dead", e.code
            return "unknown", e.code
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.gaierror):
                return "dead", "dns"
            return "unknown", str(e.reason)[:60]
        except Exception as e:  # timeouts, TLS, etc.
            return "unknown", type(e).__name__
    return "unknown", None


def main():
    data = json.loads(DATA.read_text())
    urls = sorted({e["url"] for e in data["entries"] if e.get("url")} |
                  {l["url"] for e in data["entries"] for l in e.get("links", [])})
    try:
        old = json.loads(OUT.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        old = {}
    today = dt.date.today().isoformat()
    with ThreadPoolExecutor(8) as pool:
        results = dict(zip(urls, pool.map(probe, urls)))
    new = {}
    for u, (st, code) in results.items():
        fails = old.get(u, {}).get("fails", 0) + 1 if st == "dead" else 0
        status = "dead" if fails >= 2 else ("ok" if st == "ok" else "unknown")
        new[u] = {"status": status, "code": code, "checked": today, "fails": fails}
    OUT.write_text(json.dumps(new, indent=1, sort_keys=True) + "\n")
    counts = {}
    for v in new.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print("link check:", counts)


if __name__ == "__main__":
    main()
