"""Read-only audit capability for the frozen follow-up reporting entry point.

Selection and engine modules must not import this module or its loader.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..corpus import parse_task


_DATA = Path(__file__).resolve().parent / "data"


def load_audit(data_dir=None):
    """Load only the fixed audit records, without writing or preparing any data."""
    directory = Path(data_dir) if data_dir is not None else _DATA
    records = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
    return [parse_task(record) for record in records]
