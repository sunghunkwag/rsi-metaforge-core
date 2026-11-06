"""Red-team R3, instruments (Phase 0).

(a) The same checkpoint and request sent to J twice  ->  byte-identical
    outputs, so the sleep check has no sampling noise. Checked through the
    real door (``rsi4.client``: two spawned J processes, each with its own
    hash seed) and on the sleep check itself (before == after gives no win
    and no loss).
(b) A synthetic worker over the RSS cap  ->  the watchdog stops it and logs
    the breach.
"""
import hashlib
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest

from rsi4 import client
from rsi4.judge import replay
from rsi4.tests import fixtures, workers
from rsi4.watchdog import run_watched


class DeterminismTests(unittest.TestCase):
    def test_same_request_twice_is_byte_identical(self):
        run = Path(tempfile.mkdtemp(dir=fixtures.scratch()))
        request = {"op": "evaluate", "pool": "exposed:far2",
                   "checkpoint": str(fixtures.tiny_checkpoint()),
                   "config": str(fixtures.CONFIG), "run_dir": str(run), "label": "R3a"}
        first = client.ask(request, run)
        second = client.ask(request, run)
        self.assertTrue(first["ok"], first.get("refused") or first.get("error"))
        responses = sorted(run.glob("response_*.json"))
        self.assertEqual(len(responses), 2)
        a, b = (p.read_bytes() for p in responses)
        self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())
        self.assertEqual(first["result"]["pooled"], second["result"]["pooled"])
        self.assertEqual(replay.replay(run / "judge_log.jsonl")["mismatches"], [])

    def test_sleep_check_of_an_unchanged_self_has_no_noise(self):
        run = Path(tempfile.mkdtemp(dir=fixtures.scratch()))
        checkpoint = str(fixtures.tiny_checkpoint())
        response = client.ask({"op": "sleep_check", "before": checkpoint, "after": checkpoint,
                               "config": str(fixtures.CONFIG), "run_dir": str(run),
                               "change": {"test": "R3a, identical selves"}}, run)
        self.assertTrue(response["ok"], response.get("refused") or response.get("error"))
        result = response["result"]
        self.assertEqual((result["wins"], result["losses"], result["decision"]), (0, 0, "keep"))
        self.assertEqual(result["before"]["per_seed"], result["after"]["per_seed"])


class WatchdogTests(unittest.TestCase):
    def test_worker_over_the_cap_is_stopped_and_logged(self):
        log = Path(tempfile.mkdtemp(dir=fixtures.scratch())) / "watchdog.jsonl"
        process = multiprocessing.get_context("spawn").Process(target=workers.hog, args=(400,))
        record = run_watched(process, cap_bytes=150 * 1024 ** 2, log_path=log, label="hog")
        self.assertTrue(record["monitored"])
        self.assertTrue(record["breach"])
        self.assertNotEqual(record["exitcode"], 0)
        logged = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(len(logged), 1)
        self.assertTrue(logged[0]["breach"])
        self.assertGreater(logged[0]["breach_rss_bytes"], 150 * 1024 ** 2)

    def test_worker_under_the_cap_runs_to_completion(self):
        log = Path(tempfile.mkdtemp(dir=fixtures.scratch())) / "watchdog.jsonl"
        process = multiprocessing.get_context("spawn").Process(target=workers.small, args=(1.0,))
        record = run_watched(process, cap_bytes=1024 ** 3, log_path=log, label="small")
        self.assertFalse(record["breach"])
        self.assertEqual(record["exitcode"], 0)
        self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
