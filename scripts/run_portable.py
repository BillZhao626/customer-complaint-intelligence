"""Portable smoke, using the same offline network and asset-write guards."""
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[1]
sys.argv = [str(root / 'tests/run_offline.py'), '--portable']
runpy.run_path(sys.argv[0], run_name='__main__')
