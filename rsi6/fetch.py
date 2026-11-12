"""Fetch the published data of an environment, as data, and pin it by hash.

Each environment has a manifest in ``rsi6/environments/manifests/<name>.json``: the source, the
terms under which it is published, and for every file its address, its place under
``rsi6/data/<name>/`` and its SHA-256. Data are not committed. The first fetch of a file
records its hash in the manifest; every later fetch must reproduce it. Nothing fetched is
ever executed: the adapters parse these files as text.

    python -m rsi6.fetch <name> [<name> ...]
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFESTS = os.path.join(HERE, "environments", "manifests")
DATA = os.path.join(HERE, "data")
AGENT = "research-data-check/1.0"


def manifest_path(name: str) -> str:
    return os.path.join(MANIFESTS, f"{name}.json")


def fetch(name: str, quiet: bool = False) -> dict:
    manifest = json.load(open(manifest_path(name)))
    changed = False
    for entry in manifest["files"]:
        target = os.path.join(DATA, name, entry["path"])
        if not os.path.exists(target):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            subprocess.run(["curl", "-sS", "-L", "--fail", "--max-time", "600", "-A", AGENT, "-o", target + ".part",
                            entry["url"]], check=True)
            os.replace(target + ".part", target)
        sha = hashlib.sha256(open(target, "rb").read()).hexdigest()
        if entry.get("sha256") is None:
            entry["sha256"] = sha
            changed = True
        elif entry["sha256"] != sha:
            raise RuntimeError(f"{name}/{entry['path']}: hash differs from the manifest")
        if not quiet:
            print(f"{name}/{entry['path']}  {sha[:16]}  {os.path.getsize(target)} bytes")
    if changed:
        json.dump(manifest, open(manifest_path(name), "w"), indent=1)
    return manifest


def path(name: str, relative: str) -> str:
    return os.path.join(DATA, name, relative)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        fetch(arg)
