"""One-time snapshot script for the SC2 corpus tap (Directive 2, C8).

Pins external material by SHA-256 into docs/CORPUS_MANIFEST_SC2.json:
a public shard (task material the loop may mint from) and a sealed shard
(final evaluation only). The chosen files are frozen exploration-side
artifacts already committed and hash-stable forever; nothing here touches
the human instrument stores. After the spec freeze, the battery verifies
every hash and aborts on mismatch (invariant I20).

Run once from the repository root; the manifest is then committed and its
own SHA-256 is pinned in the runtime (SC2_CORPUS_MANIFEST_SHA256).
"""
import hashlib
import json
import os

PUBLIC = [
    os.path.join("docs", "exploration_archive_phaseD.json"),
    os.path.join("docs", "anchor_report_phaseE.json"),
]
SEALED = [
    os.path.join("docs", "exploration_archive_phaseG.json"),
    os.path.join("docs", "anchor_report_phaseG.json"),
]


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    manifest = {
        "meta": {
            "spec": "SC2-1",
            "note": "frozen exploration-side artifacts; public shard "
                    "supplies distributional task material, sealed shard "
                    "is final-evaluation only (M7)",
        },
        "public": {p: sha(p) for p in PUBLIC},
        "sealed": {p: sha(p) for p in SEALED},
    }
    out = os.path.join("docs", "CORPUS_MANIFEST_SC2.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(out, sha(out))


if __name__ == "__main__":
    main()
