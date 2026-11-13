"""J's registry: its seed, its fixed constants, and the hash of its own files.

Everything here is fixed at the Phase 0 commit (OWNER_DIRECTIVE.md §5, §6).
Nothing the system under evaluation controls can change a value here: no
agent module may import this package (``audit.py``), and the agent process
blocks opening any file under ``rsi4/judge/`` at run time (``audit.guard``).

**J's seed** lives in ``seed.json`` beside this module. Only the judge
process opens it: the pool builder uses it for the stage split and every
draw. The agent's environment never holds it.

**Integrity.** ``MANIFEST.sha256`` lists the SHA-256 of every file under
``rsi4/judge/`` (except the manifest itself and bytecode caches) and of the
agent-facing stage-train file the builder writes. ``verify_manifest`` checks
the live files against it; ``tree_digest`` is the single hash J records at a
run's start and compares at its end (``evaluate.run_start`` / ``run_end``).
A mismatch voids the run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

JUDGE_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = JUDGE_DIR.parent
REPO_DIR = PACKAGE_DIR.parent
POOLS_DIR = JUDGE_DIR / "pools"
SEED_FILE = JUDGE_DIR / "seed.json"
MANIFEST_FILE = JUDGE_DIR / "MANIFEST.sha256"
STAGE_TRAIN_FILE = PACKAGE_DIR / "data" / "stage_train.json"

# ---- evaluation (§5, §6, F7, F8) -------------------------------------------
EVAL_SEEDS = (11, 22, 33)          # the registered seeds; never changed
B_EVAL = 64                        # held-out candidates per task
SOLVED_MIN_SEEDS = 2               # a task counts as solved on >= 2 of 3 seeds

# ---- decisions -------------------------------------------------------------
DELTA_SLEEP = 2                    # sleep check: revert when losses - wins >= 2
ALPHA = 0.05                       # exact one-sided sign test level
REGRESSION_BUDGET = 5              # loop-4 confirmation: at most 5 losses
FINAL_MAX_LOSSES = 8               # Gate 4: at most 8 losses on the final test

# ---- pools (§4) --------------------------------------------------------------
STAGES = 3
STAGE_TRAIN = 36
STAGE_EVAL = 100
PROBE = 60
SELECTION = 100
CONFIRMATION = 200
ROUNDS = 3
FINAL_TWO_STAGE = 200
FINAL_THREE_STAGE = 100


def judge_seed() -> int:
    """J's own seed. Opened by the judge process only."""
    return int(json.loads(SEED_FILE.read_text(encoding="utf-8"))["judge_seed"])


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_paths(judge_dir: Path = JUDGE_DIR) -> list[Path]:
    """Every file J's integrity covers, in a fixed order."""
    judge_dir = Path(judge_dir)
    paths = [p for p in judge_dir.rglob("*") if p.is_file()
             and p.name != MANIFEST_FILE.name and "__pycache__" not in p.parts
             and p.suffix != ".pyc"]
    stage_train = judge_dir.parent / "data" / STAGE_TRAIN_FILE.name
    if stage_train.exists():
        paths.append(stage_train)
    return sorted(paths, key=lambda p: _relative(p, judge_dir))


def _relative(path: Path, judge_dir: Path) -> str:
    path, judge_dir = Path(path).resolve(), Path(judge_dir).resolve()
    try:
        return path.relative_to(judge_dir).as_posix()
    except ValueError:
        return "../" + path.relative_to(judge_dir.parent).as_posix()


def manifest_lines(judge_dir: Path = JUDGE_DIR) -> list[str]:
    return [f"{file_sha256(p)}  {_relative(p, judge_dir)}" for p in manifest_paths(judge_dir)]


def write_manifest(judge_dir: Path = JUDGE_DIR) -> str:
    text = "\n".join(manifest_lines(judge_dir)) + "\n"
    (Path(judge_dir) / MANIFEST_FILE.name).write_text(text, encoding="utf-8")
    return text


def verify_manifest(judge_dir: Path = JUDGE_DIR) -> list[str]:
    """Paths whose content differs from the manifest, or that it misses; [] when intact."""
    judge_dir = Path(judge_dir)
    recorded = {}
    for line in (judge_dir / MANIFEST_FILE.name).read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split("  ", 1)
            recorded[name] = digest
    live = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in manifest_lines(judge_dir)}
    return sorted(name for name in set(recorded) | set(live) if recorded.get(name) != live.get(name))


def tree_digest(judge_dir: Path = JUDGE_DIR) -> str:
    """One hash of J's covered files and of the manifest itself."""
    judge_dir = Path(judge_dir)
    digest = hashlib.sha256()
    for line in manifest_lines(judge_dir):
        digest.update(line.encode("utf-8") + b"\n")
    manifest = judge_dir / MANIFEST_FILE.name
    digest.update(manifest.read_bytes() if manifest.exists() else b"")
    return digest.hexdigest()


def canonical(payload) -> bytes:
    """The byte form every J hash and comparison uses."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      default=str).encode("ascii")
