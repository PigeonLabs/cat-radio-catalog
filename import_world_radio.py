"""Build the overseas catalog from Radio Browser, retaining previously saved station IDs."""
import argparse
import csv
import gzip
import ipaddress
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

APP = Path(__file__).resolve().parent
VERIFIED = APP / "data/verified.csv"
REVIEW = APP / "data/world_radio_review.csv.gz"
OUTPUT = APP / "world.json.gz"
CODECS = {"MP3", "AAC", "AAC+", "OGG", "FLAC", "OPUS", "WMA"}


def public_stream(url):
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").rstrip(".").lower()
        if (parts.scheme not in {"http", "https"} or parts.username or parts.password
                or "." not in host or host.endswith((".local", ".localhost"))):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return not re.fullmatch(r"[0-9.]+", host)
    except ValueError:
        return False


def entry_url(row):
    resolved, registered = row["url_resolved"], row["url"]
    # Reopen the registered playlist/redirect on each listen. Signed URLs
    # and per-listener tracking tokens in resolved media expire.
    if resolved and "?" in resolved and registered != resolved and public_stream(registered):
        return registered
    return resolved or registered


def eligible(row):
    return (row["countrycode"].upper() != "KR" and row["lastcheckok"]
            and row["codec"].upper() in CODECS and public_stream(entry_url(row))
            and row["name"].strip() and not re.search(r"\bTV\b", row["name"], re.I))


def build(snapshot, previous, out):
    # id, name, country, primary URL, description; votes are sorted separately.
    rows, votes, alias = {}, {}, {}
    if previous:
        old = json.loads(gzip.decompress(previous.read_bytes()))
        rows = {r[0]: list(r) for r in zip(*old[2:7])}
        if len(old) > 7:
            alias.update(old[7]["aliases"])

    with VERIFIED.open(encoding="utf-8-sig") as source:
        for r in csv.DictReader(source):
            if r["국가코드"] == "KR":
                continue
            key = "radio-db-" + r["기존_통합목록_ID"]
            rows[key] = [key, r["방송명"], r["국가코드"], r["스트림_URL"], r["방송사_네트워크"]]

    previous_ids = set(rows)
    curated_urls = {r[3] for k, r in rows.items() if k.startswith("radio-db-")}
    for r in filter(eligible, json.loads(snapshot.read_text())):
        key = "rb-" + r["stationuuid"]
        # A former alias can later acquire a genuinely different stream.
        alias.pop(key, None)
        url = r["url_resolved"] if r["url_resolved"] in curated_urls else entry_url(r)
        cc = r["countrycode"].upper()
        rows[key] = [key, r["name"].strip(), cc if re.fullmatch("[A-Z]{2}", cc) else "ZZ", url, r["codec"]]
        votes[key] = max(0, r["votes"])

    # When equivalent listings converge on one URL, retain their IDs as
    # aliases. Old favorites and presets still resolve after a catalog refresh.
    by_url = {}
    for key in sorted(rows, key=lambda k: (not k.startswith("radio-db-"), k not in previous_ids, k)):
        url = rows[key][3]
        if url in by_url:
            owner = by_url[url]
            alias[key] = owner
            votes[owner] = max(votes.get(key, 0), votes.get(owner, 0))
        else:
            by_url[url] = key
    catalog = sorted((rows[k] for k in by_url.values()), key=lambda r: r[3])
    indexes = {r[0]: i for i, r in enumerate(catalog)}
    for key in list(alias):
        dest = alias[key]
        while dest in alias and dest not in indexes:
            dest = alias[dest]
        alias[key] = dest
    assert all(k not in indexes and v in indexes for k, v in alias.items())

    extras = {}
    if REVIEW.exists():
        with gzip.open(REVIEW, "rt", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                key = r["id"]
                if key in indexes and catalog[indexes[key]][3] == r["primary"]:
                    extras[indexes[key]] = [float(r["fm_MHz"]) if r["fm_MHz"] else None,
                                           r["band"] or None, json.loads(r["backups"])]
    order = sorted(range(len(catalog)), key=lambda i: (-votes.get(catalog[i][0], 0),
                   catalog[i][1].casefold(), catalog[i][0]))
    codes = sorted({r[2] for r in catalog})
    script = """const names=['ko','en'].map(locale=>new Intl.DisplayNames([locale],{type:'region'}));
console.log(JSON.stringify(Object.fromEntries(JSON.parse(process.argv[1]).map(code=>
 [code,names.map(n=>n.of(code))]))));"""
    countries = json.loads(subprocess.check_output(["node", "-e", script, json.dumps(codes)]))
    data = [countries, order, *zip(*catalog), {"stations": extras, "aliases": dict(sorted(alias.items()))}]
    out.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(),
                                  compresslevel=9, mtime=0))
    print(f"{len(catalog)} streams, {len(alias)} saved ID aliases, {len(codes)} countries/regions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--previous", type=Path, help="Previously shipped asset (may equal output)")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.snapshot, args.previous, args.output)
