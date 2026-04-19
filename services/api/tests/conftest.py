import sys
from pathlib import Path

# Ensure the app package is importable from the services/api root
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))
