"""HTTP-layer smoke tests.

The behavioural suite exercises the prompt/LLM modules directly; these tests
cover the wiring the refactor touched — that the app assembles, routers mount at
their expected paths, and non-LLM endpoints respond. No LLM key required.
"""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_config_exposes_feature_flags():
    body = client.get("/api/config").json()
    assert "provider" in body
    assert "enabled_tracks" in body


def test_catalog_endpoints_respond():
    for path in (
        "/api/catalog/tracks",
        "/api/catalog/companies",
        "/api/catalog/difficulties",
        "/api/catalog/hint-tiers",
        "/api/interview/focuses",
    ):
        assert client.get(path).status_code == 200, path


def test_protected_endpoint_requires_auth():
    resp = client.get("/api/stats")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Log in to see your progress."


def test_all_expected_routes_mounted():
    paths = {r.path for r in app.routes}
    for expected in (
        "/api/chat",
        "/api/interview/grade",
        "/api/auth/login",
        "/api/resume",
        "/api/resume/upload",
        "/api/history/{username}",
        "/api/sessions",
    ):
        assert expected in paths, expected
