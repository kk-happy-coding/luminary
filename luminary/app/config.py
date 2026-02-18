import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("LUMINARY_DATA_DIR", "/app/data"))
