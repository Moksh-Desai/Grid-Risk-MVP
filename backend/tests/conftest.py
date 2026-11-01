import os
import sys
import tempfile
from pathlib import Path

# Isolated, small dataset so the suite runs in well under a minute.
os.environ["GRIDRISK_DATA_DIR"] = tempfile.mkdtemp(prefix="gridrisk-test-")
os.environ["GRIDRISK_SYNTHETIC_N"] = "6000"
os.environ.pop("DATABASE_URL", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.ml import predictor

    with TestClient(app) as c:
        predictor.load_now()  # block until models are ready
        yield c
