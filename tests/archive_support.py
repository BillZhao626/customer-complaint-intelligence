"""Explicit opt-in checks for non-redistributed historical research archives."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def requires_archive(*paths):
    missing = [p for p in paths if not (ROOT / p).exists()]
    return unittest.skipIf(bool(missing), 'Private historical archive required: ' + ', '.join(missing))
