def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert "database" in body
    assert "chromadb" in body


def test_health_no_auth_required(client):
    response = client.get("/health")
    assert response.status_code == 200
