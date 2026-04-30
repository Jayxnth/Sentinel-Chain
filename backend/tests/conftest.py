import os
import sys
from pathlib import Path

# Set test env vars BEFORE importing backend
os.environ["API_KEY"] = "test-api-key-12345"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["GOOGLE_API_KEY"] = "fake-key-for-tests"
os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"

# Add repo root to sys.path so backend imports work
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.main import app
from backend.db.database import get_db
from backend.db.models import Base


# Use a single in-memory DB for the whole test session, reset
# between tests via the fixture below
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_session_maker = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    """Drop and recreate all tables before each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


async def override_get_db():
    async with test_session_maker() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def api_key():
    return "test-api-key-12345"


@pytest.fixture
def auth_headers(api_key):
    return {"X-API-Key": api_key}


@pytest.fixture(autouse=True)
def mock_ai_pipeline():
    """Mock out Gemini and HuggingFace so tests don't hit network."""
    fake_report = {
        "summary": "Test summary",
        "severity": "MEDIUM",
        "findings": ["Test finding 1", "Test finding 2"],
        "recommendations": ["Test rec 1"],
    }

    with patch("backend.routers.ingest.asyncio.to_thread") as mock_thread:
        # First call is root_ingest.ingest_logs (returns True)
        # Second call is analyze_logs (returns fake_report)
        async def fake_to_thread(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if "ingest_logs" in name:
                return True
            if "analyze_logs" in name:
                return fake_report
            return None
        mock_thread.side_effect = fake_to_thread

        with patch("backend.routers.upload.asyncio.to_thread") as mock_upload_thread:
            mock_upload_thread.side_effect = fake_to_thread
            yield
