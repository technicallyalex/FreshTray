"""Allow unittest and standalone smoke checks to import the editable src tree."""
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SOURCE))
