"""Build and validate the assets for a tagged station catalog release."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path

from import_world_radio import APP, build, eligible, public_stream


def domestic():
    stations = []
    with (APP / "data/korea.csv").open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            row["backups"] = json.loads(row["backups"])
            row["fm_MHz"] = float(row["fm_MHz"]) if row["fm_MHz"] else None
            if (not row["id"] or not row["name"] or
                    row["type"] not in {"direct", "plainText", "kbs", "kbsWorld"} or
                    not all(public_stream(url) for url in [row["primary"], *row["backups"]]) or
                    (row["fm_MHz"] is not None and not 87.5 <= row["fm_MHz"] <= 108)):
                raise ValueError(f"Invalid domestic station {row['id']}")
            stations.append(row)
    if (len({row["id"] for row in stations}) != len(stations)
            or not any(row["fm_MHz"] for row in stations)):
        raise ValueError("Domestic station IDs or FM list invalid")
    return stations


def build_release(snapshot, previous, output, repo, tag):
    output.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(gzip.decompress(previous.read_bytes()))
    # The importer retains historical IDs, so check the upstream payload itself
    # to catch truncated mirrors before a partial ranking can be published.
    fresh = json.loads(snapshot.read_bytes())
    if sum(1 for row in fresh if eligible(row)) < len(baseline[1]) * 0.65:
        raise ValueError("Radio Browser snapshot unexpectedly small")
    del fresh
    world = output / "world.json.gz"
    build(snapshot, previous, world)
    catalog = json.loads(gzip.decompress(world.read_bytes()))
    n = len(catalog[2])
    ids = set(catalog[2])
    if (n != len(ids) or any(len(column) != n for column in catalog[3:7])
            or sorted(catalog[1]) != list(range(n))
            or not set(catalog[4]) <= set(catalog[0])
            or not set(catalog[7]["aliases"].values()) <= ids):
        raise ValueError("Invalid world catalog indexes or aliases")
    kr = output / "kr.json.gz"
    kr.write_bytes(gzip.compress(json.dumps(domestic(), ensure_ascii=False,
                                            separators=(",", ":")).encode(), mtime=0))
    files = {}
    for key, path in [("kr", kr), ("world", world)]:
        files[key] = {"url": f"https://github.com/{repo}/releases/download/{tag}/{path.name}",
                      "bytes": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {"schema": 1, "version": tag, "files": files}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--previous", type=Path, default=APP / "data/world_seed.json.gz")
    parser.add_argument("--output", type=Path, default=APP / "dist")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "PigeonLabs/cat-radio-catalog"))
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    build_release(args.snapshot, args.previous, args.output, args.repo, args.tag)
