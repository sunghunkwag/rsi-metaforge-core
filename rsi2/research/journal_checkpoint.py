"""Lossless append-only checkpoints for the recursive TRAIN controller.

``JournalCheckpoint(path)`` is a callable checkpoint callback. The file at
``path`` is a small storage manifest; use ``reconstruct(path).record`` to read
its original JSON record. Completed dictionaries under a ``search`` key and
rows already appended to the root ``generations`` list must be immutable.
Those objects are retained by identity and serialized once. Mutable enclosing
rows, verification results, counters and the current state are saved each time.
No input object is mutated and no corpus, evaluator or search engine is loaded.

The journal is flushed and fsynced before the atomic manifest commit. A reader
uses only its committed prefix. Uncommitted suffixes produce explicitly partial,
lower-bound evidence; malformed committed data raises JournalCorruption.
Writer CPU includes failed writes; reconstruction reports its own CPU separately.
Single-writer use is required. Existing paths are never overwritten on opening.
"""
from __future__ import annotations

from dataclasses import dataclass, is_dataclass
import json
import os
from pathlib import Path
import time

from ..terms import Term


SCHEMA = "rsi2-immutable-journal-v1"
_REF, _DICT, _LIST = "@rsi2-journal-ref", "@rsi2-journal-dict", "@rsi2-journal-list"


class JournalCorruption(ValueError):
    """Committed evidence cannot be reconstructed faithfully."""


@dataclass(frozen=True)
class Recovery:
    record: dict
    interrupted: bool
    committed_bytes: int
    ignored_bytes: int
    journal_objects: int
    cpu_seconds: float
    wall_seconds: float


def _default(value):
    if isinstance(value, Term):
        return value.to_dict()
    if is_dataclass(value) and not isinstance(value, type):
        return vars(value)
    raise TypeError(f"unsupported checkpoint value: {type(value).__name__}")


def _key(value):
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return json.dumps(value, allow_nan=False)
    raise TypeError(f"unsupported checkpoint key: {type(value).__name__}")


class _CountingTextWriter:
    def __init__(self, stream, metrics, field):
        self.stream, self.metrics, self.field = stream, metrics, field

    def write(self, value):
        encoded = value.encode("utf-8")
        written = self.stream.write(encoded)
        self.metrics[self.field] += written
        return len(value)


def _dump(value, stream, metrics, field):
    writer = _CountingTextWriter(stream, metrics, field)
    json.dump(value, writer, default=_default, separators=(",", ":"), allow_nan=False)
    writer.write("\n")


class JournalCheckpoint:
    """Append immutable completed operations and atomically save the live root.

    ``metrics`` returns a fresh telemetry dictionary. ``close()`` releases the
    journal handle; ``reconstruct`` can also run while the writer remains open.
    CPU/process watchdogs around the controller must count persistence normally.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.journal_path = self.path.with_name(self.path.name + ".journal.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() or self.journal_path.exists():
            raise FileExistsError(f"checkpoint already exists: {self.path}")
        self._stream = self.journal_path.open("xb")
        self._cache = {}  # Strong object references prevent Python id reuse.
        self._pending = {}
        self._committed_bytes = self._sequence = 0
        self._closed = False
        self._broken = False
        self._root_published = False
        self._metrics = {
            "checkpoint_calls": 0, "successful_commits": 0, "failed_commits": 0,
            "journal_entries_written": 0, "journal_bytes_written": 0,
            "checkpoint_bytes_written": 0, "archived_searches": 0,
            "archived_generations": 0, "cpu_seconds": 0.0, "wall_seconds": 0.0,
        }

    @property
    def metrics(self):
        return dict(self._metrics)

    def close(self):
        if not self._closed:
            self._stream.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _reference(self, value):
        saved = self._pending.get(id(value), self._cache.get(id(value)))
        return {_REF: saved[1]} if saved is not None and saved[0] is value else None

    def _archive(self, value, kind):
        previous = self._reference(value)
        if previous is not None:
            return previous
        # Search is already a completed JSON view; stream it once without a
        # second whole-search copy. Generation traversal replaces its searches.
        payload = value if kind == "search" else self._encode(value, archive_search=False)
        sequence = self._sequence + len(self._pending) + 1
        entry = {"sequence": sequence, "kind": kind,
                 "encoding": "json" if kind == "search" else "tagged", "value": payload}
        _dump(entry, self._stream, self._metrics, "journal_bytes_written")
        self._metrics["journal_entries_written"] += 1
        self._pending[id(value)] = (value, sequence, kind)
        return {_REF: sequence}

    def _encode(self, value, *, archive_search=True, key=None, active=None):
        if isinstance(value, dict):
            previous = self._reference(value)
            if previous is not None:
                return previous
            if archive_search and key == "search":
                return self._archive(value, "search")
            active = set() if active is None else active
            if id(value) in active:
                raise ValueError("circular checkpoint dictionary")
            active.add(id(value))
            try:
                return {_DICT: [[_key(name), self._encode(item, key=name, active=active)]
                                for name, item in value.items()]}
            finally:
                active.remove(id(value))
        if isinstance(value, (list, tuple)):
            active = set() if active is None else active
            if id(value) in active:
                raise ValueError("circular checkpoint list")
            active.add(id(value))
            try:
                return {_LIST: [self._encode(item, active=active) for item in value]}
            finally:
                active.remove(id(value))
        if isinstance(value, Term) or (is_dataclass(value) and not isinstance(value, type)):
            return self._encode(_default(value), active=active)
        return value

    def _encode_root(self, record):
        if not isinstance(record, dict):
            raise TypeError("checkpoint root must be a dictionary")
        items = []
        for name, value in record.items():
            if name == "generations":
                if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
                    raise TypeError("completed generations must be a list of dictionaries")
                encoded = {_LIST: [self._archive(row, "generation") for row in value]}
            else:
                encoded = self._encode(value, key=name)
            items.append([_key(name), encoded])
        return {_DICT: items}

    def _commit_root(self, manifest):
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            with temporary.open("wb") as stream:
                _dump(manifest, stream, self._metrics, "checkpoint_bytes_written")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            # Record publication before any later bookkeeping or filesystem
            # operation can fail. A published manifest owns its durable prefix.
            self._root_published = True
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _adopt_commit(self, end):
        self._committed_bytes = end
        self._sequence += len(self._pending)
        self._cache.update(self._pending)
        for _, _, kind in self._pending.values():
            self._metrics["archived_searches" if kind == "search" else "archived_generations"] += 1
        self._metrics["successful_commits"] += 1
        self._pending = {}

    def _sync_directory(self):
        descriptor = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def __call__(self, record):
        if self._closed or self._broken:
            raise ValueError("checkpoint writer is closed or damaged")
        started_cpu, started_wall = time.process_time(), time.perf_counter()
        self._metrics["checkpoint_calls"] += 1
        committed = False
        self._root_published = False
        self._pending = {}
        try:
            root = self._encode_root(record)
            self._stream.flush()
            os.fsync(self._stream.fileno())
            end = self._stream.tell()
            manifest = {"schema": SCHEMA, "journal": self.journal_path.name,
                        "committed_bytes": end, "objects": self._sequence + len(self._pending),
                        "root": root}
            self._commit_root(manifest)
            # After replace, readers may already see this prefix. Never truncate
            # it if directory synchronization subsequently reports a failure.
            committed = True
            self._adopt_commit(end)
            self._sync_directory()
        except Exception:
            self._metrics["failed_commits"] += 1
            if self._root_published and not committed:
                self._adopt_commit(end)
                committed = True
            if not committed:
                try:
                    self._stream.flush()
                    self._stream.truncate(self._committed_bytes)
                    self._stream.seek(self._committed_bytes)
                    self._stream.flush()
                    os.fsync(self._stream.fileno())
                except Exception:
                    self._broken = True
                    raise
                finally:
                    self._pending = {}
            raise
        finally:
            self._metrics["cpu_seconds"] += time.process_time() - started_cpu
            self._metrics["wall_seconds"] += time.perf_counter() - started_wall


def _integer(value, label):
    if type(value) is not int or value < 0:
        raise JournalCorruption(f"invalid {label}")
    return value


def _decode(value, objects):
    if not isinstance(value, dict):
        if isinstance(value, list):
            raise JournalCorruption("untagged list in encoded checkpoint")
        return value
    if len(value) != 1:
        raise JournalCorruption("invalid encoded checkpoint object")
    if _REF in value:
        sequence = _integer(value[_REF], "reference")
        if sequence not in objects:
            raise JournalCorruption("reference outside committed earlier objects")
        return objects[sequence]
    if _LIST in value:
        if not isinstance(value[_LIST], list):
            raise JournalCorruption("invalid encoded list")
        return [_decode(item, objects) for item in value[_LIST]]
    if _DICT in value:
        if not isinstance(value[_DICT], list):
            raise JournalCorruption("invalid encoded dictionary")
        result = {}
        for pair in value[_DICT]:
            if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
                raise JournalCorruption("invalid encoded dictionary item")
            result[pair[0]] = _decode(pair[1], objects)
        return result
    raise JournalCorruption("unknown encoded checkpoint tag")


def reconstruct(path):
    """Recover exact JSON values/order, failing closed on committed corruption.

    An extra journal suffix is ignored, and the returned record is explicitly
    partial/lower-bound even if the last committed root had claimed completion.
    Interrupted recovery diagnostics are returned separately in ``Recovery``.
    """
    started_cpu, started_wall = time.process_time(), time.perf_counter()
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as stream:
            manifest = json.load(stream)
        if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
            raise JournalCorruption("unsupported checkpoint manifest")
        journal_name = manifest.get("journal")
        if (not isinstance(journal_name, str) or Path(journal_name).name != journal_name
                or journal_name != path.name + ".journal.jsonl"):
            raise JournalCorruption("invalid checkpoint journal path")
        committed = _integer(manifest.get("committed_bytes"), "committed byte count")
        expected_objects = _integer(manifest.get("objects"), "object count")
        journal = path.with_name(journal_name)
        physical = journal.stat().st_size
        if physical < committed:
            raise JournalCorruption("journal is shorter than committed prefix")
        objects, consumed = {}, 0
        with journal.open("rb") as stream:
            while consumed < committed:
                line = stream.readline(committed - consumed + 1)
                if not line.endswith(b"\n") or len(line) > committed - consumed:
                    raise JournalCorruption("truncated committed journal line")
                entry = json.loads(line)
                if (not isinstance(entry, dict) or set(entry) != {"sequence", "kind", "encoding", "value"}
                        or type(entry["sequence"]) is not int or entry["sequence"] != len(objects) + 1):
                    raise JournalCorruption("invalid journal sequence/entry")
                if entry["kind"] == "search" and entry["encoding"] == "json":
                    value = entry["value"]
                    if not isinstance(value, dict):
                        raise JournalCorruption("search object must be a dictionary")
                elif entry["kind"] == "generation" and entry["encoding"] == "tagged":
                    value = _decode(entry["value"], objects)
                    if not isinstance(value, dict):
                        raise JournalCorruption("generation object must be a dictionary")
                else:
                    raise JournalCorruption("invalid journal kind/encoding")
                objects[entry["sequence"]] = value
                consumed += len(line)
        if len(objects) != expected_objects:
            raise JournalCorruption("committed journal object count differs")
        record = _decode(manifest.get("root"), objects)
        if not isinstance(record, dict):
            raise JournalCorruption("checkpoint root must be a dictionary")
        interrupted = physical > committed
        if interrupted:
            record["status"] = "partial"
            record["candidate_evaluations_scope"] = "completed_operations_lower_bound"
            if "rsi_success" in record:
                record["rsi_success"] = False
            record["journal_recovery"] = {
                "reason": "uncommitted journal suffix ignored",
                "ignored_bytes": physical - committed,
                "accounting_scope": "committed_operations_lower_bound",
            }
        return Recovery(record, interrupted, committed, physical - committed, len(objects),
                        time.process_time() - started_cpu, time.perf_counter() - started_wall)
    except JournalCorruption:
        raise
    except (OSError, ValueError, TypeError, RecursionError) as error:
        raise JournalCorruption(f"cannot reconstruct committed checkpoint: {error}") from error
