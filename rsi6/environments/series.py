"""Kinds of forecasting problem made from the Monash Time Series Forecasting Archive.

Published form: one ``.tsf`` file per data set, zipped, on Zenodo (Godahewa et al. 2021;
https://forecastingdata.org): a header and one line per series with its values in time order.
The files are fetched as data, by hash, and read as text. A *kind* is one or more of these
files, listed in its manifest.

Problem form: prediction, ordered. From every file a fixed sample of at most 48 series is used
(the first in the order of the SHA-256 of the series' name). The last ``h`` values of a series
are the queries and what comes before them is the history, cut to its last 240 values (observed
entities: attribute the position in time, target the value). ``h`` is the horizon the file's
header states, or the one its manifest gives, and at most 48. A series whose history is shorter
than twice ``h`` or than 12 values, or that has a missing value, is not used.

Reference: the real continuation, which the scorer alone reads. The score is one minus the
symmetric mean absolute percentage error over 200, as for the M4 series
(``rsi6/environments/forecasting.py``). The threshold is an operating point, not an external
fact. When a kind has several files, training and fresh series come from different files
(``group`` is the file).
"""
from __future__ import annotations

import hashlib
import io
import zipfile

import numpy as np

from rsi6 import fetch
from rsi6.environments.forecasting import smape
from rsi6.kernel.environment import Environment
from rsi6.kernel.problem import PredictProblem

PER_FILE, MAX_HISTORY, MAX_HORIZON = 48, 240, 48


def read_tsf(path: str):
    """``(header horizon or None, {series name: values})`` of the one ``.tsf`` file in a zip."""
    with zipfile.ZipFile(path) as archive:
        inner = [n for n in archive.namelist() if n.endswith(".tsf")]
        text = io.TextIOWrapper(archive.open(inner[0]), encoding="latin-1")
        horizon, attributes, series, in_data = None, [], {}, False
        for line in text:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not in_data:
                low = line.lower()
                if low.startswith("@attribute"):
                    attributes.append(line.split()[1])
                elif low.startswith("@horizon"):
                    horizon = int(line.split()[1])
                elif low.startswith("@data"):
                    in_data = True
                continue
            parts = line.split(":")
            name = parts[0] if attributes else str(len(series))
            values = parts[-1].split(",")
            if "?" in values:
                continue
            series[name] = np.array([float(v) for v in values])
    return horizon, series


class Series(Environment):
    form = "predict"
    threshold = 0.9
    anchor = "an operating point: a mean score of 0.9, that is a symmetric mean absolute percentage error of 20"

    def __init__(self):
        manifest = fetch.fetch(self.name, quiet=True)
        self.series, self.file_of, self.refused = {}, {}, 0
        for entry in manifest["files"]:
            stated, series = read_tsf(fetch.path(self.name, entry["path"]))
            if not (entry.get("horizon") or stated):
                raise RuntimeError(f"{self.name}/{entry['path']}: no horizon in the file's header or in the manifest")
            h = int(min(entry.get("horizon") or stated, MAX_HORIZON))
            label = entry["path"][:-4]
            usable = {}
            for name, values in series.items():
                history = values[:-h]
                if len(history) < max(2 * h, 12) or not np.all(np.isfinite(values)):
                    self.refused += 1
                    continue
                usable[name] = (history[-MAX_HISTORY:], values[-h:])
            for name in sorted(usable, key=lambda k: hashlib.sha256(f"{label}|{k}".encode()).hexdigest())[:PER_FILE]:
                self.series[f"{label}/{name}"] = usable[name]
                self.file_of[f"{label}/{name}"] = label

    def instance_ids(self):
        return sorted(self.series)

    def reference(self, instance_id):
        return self.series[instance_id][1].tolist()

    def group(self, instance_id):
        return self.file_of[instance_id]

    def problem(self, instance_id, meter, seed, training):
        history, future = self.series[instance_id]
        t = len(history)
        problem = PredictProblem(np.arange(t, dtype=float)[:, None], history, np.arange(t, t + len(future), dtype=float)[:, None],
                                 ordered=True, target=future if training else None, meter=meter)
        return problem, (lambda answer: np.asarray(answer, dtype=float))

    def score(self, instance_id, answer):
        future = self.series[instance_id][1]
        a = np.asarray(answer, dtype=float)
        if a.shape != future.shape or not np.all(np.isfinite(a)):
            return 0.0
        return float(1.0 - min(smape(a, future), 200.0) / 200.0)


class Cif(Series):
    name = category = "cif"


class Nn5(Series):
    name = category = "nn5"


class FredMd(Series):
    name = category = "fredmd"
