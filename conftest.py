import sys
import os

# Ensure repo root is on sys.path for pytest runs so top-level packages (providers, schemas, config) import correctly
REPO_ROOT = os.path.dirname(__file__)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
