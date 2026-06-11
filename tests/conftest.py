import os

import psycopg2
import psycopg2.extras
import pytest
from fastapi.testclient import TestClient

# Use TEST_DATABASE_URL if set; otherwise skip DB tests
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "")

if TEST_DB_URL:
    os.environ["DATABASE_URL"] = TEST_DB_URL
    os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
    os.environ["INTERNAL_JOB_SECRET"] = "test-internal-secret"
    os.environ["FRONTEND_URL"] = "http://localhost:5173"


@pytest.fixture(scope="session")
def test_db_conn():
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    conn = psycopg2.connect(TEST_DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def client():
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    from app.main import app
    with TestClient(app) as c:
        yield c

