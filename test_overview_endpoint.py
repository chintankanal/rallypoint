#!/usr/bin/env python3
"""
Test the /api/v1/overview endpoint for public landing page stats.
"""
import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:ocean202@localhost:5432/jlrs")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("INTERNAL_JOB_SECRET", "test-internal")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_pool, close_pool
from app.config import settings


def test_overview_endpoint():
    init_pool(settings.database_url)
    try:
        client = TestClient(app)
        response = client.get("/api/v1/overview")
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data.get("total_players"), int)
        assert isinstance(data.get("matches_processed"), int)
        assert isinstance(data.get("participating_academies"), int)
        print("Overview endpoint returned valid stats.")

        redirect_response = client.get("/overview", allow_redirects=False)
        assert redirect_response.status_code in (301, 302, 307, 308), redirect_response.text
        assert redirect_response.headers["location"] == settings.frontend_url
        print("Direct /overview browser path redirects to frontend landing page.")
    finally:
        close_pool()


def main():
    try:
        test_overview_endpoint()
        print("\n✓ Overview endpoint test PASSED")
        return 0
    except AssertionError as exc:
        print(f"\n✗ Overview endpoint test FAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"\n✗ Test error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
