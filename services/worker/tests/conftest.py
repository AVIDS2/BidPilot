import sys
from pathlib import Path

# Ensure the app package is importable from the services/worker root
worker_root = Path(__file__).resolve().parent.parent
if str(worker_root) not in sys.path:
    sys.path.insert(0, str(worker_root))
