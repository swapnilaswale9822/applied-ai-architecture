"""Put the code directories on sys.path so packages import by name in tests."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for d in (HERE, os.path.join(HERE, "evaluation-harness"), os.path.join(HERE, "governance-layer")):
    if d not in sys.path:
        sys.path.insert(0, d)
