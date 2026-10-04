"""API-level tests using FastAPI TestClient."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "mock_llm" in body


def test_index_renders():
    res = client.get("/")
    assert res.status_code == 200
    assert "Self-Healing Code Sandbox" in res.text


def test_heal_endpoint_add():
    res = client.post(
        "/heal",
        json={
            "task_description": "Write a function add(a, b) that returns the sum of two numbers."
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["attempts"] == 2
    assert "def add" in body["implementation_code"]


def test_heal_rejects_short_task():
    res = client.post("/heal", json={"task_description": "ab"})
    assert res.status_code == 422
