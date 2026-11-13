from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

TEST_ROOT = Path(tempfile.mkdtemp(prefix="civicops-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(TEST_ROOT / "uploads")
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["PASSWORD_ITERATIONS"] = "1000"
os.environ["PUBLIC_REPORT_RATE_LIMIT_PER_HOUR"] = "1000"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
import io  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import DEMO_PASSWORD, seed_demo_data  # noqa: E402
from app.services.rate_limit import clear_rate_limits  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    shutil.rmtree(settings.upload_path, ignore_errors=True)
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    clear_rate_limits()
    with SessionLocal() as db:
        seed_demo_data(db)
    with TestClient(app) as test_client:
        yield test_client
    clear_rate_limits()


@pytest.fixture()
def db():
    with SessionLocal() as session:
        yield session


def login_headers(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def jpeg_bytes(color: tuple[int, int, int] = (80, 120, 80)) -> bytes:
    image = Image.new("RGB", (160, 120), color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def refresh_session(session) -> None:
    session.rollback()
    session.expire_all()
