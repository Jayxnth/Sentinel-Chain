def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_no_auth_required(client):
    # No X-API-Key header sent, should still work
    response = client.get("/health")
    assert response.status_code == 200
