import os


def test_query_empty_db_returns_200(client, auth_headers, monkeypatch):
    # Force the empty-DB short-circuit regardless of dev machine state.
    # /query checks os.path.exists(chroma_db) at runtime.
    real_exists = os.path.exists

    def fake_exists(path):
        if "chroma_db" in str(path):
            return False
        return real_exists(path)

    monkeypatch.setattr("backend.routers.query.os.path.exists", fake_exists)

    payload = {"question": "any threats?"}
    response = client.post("/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "citations" in body
    assert isinstance(body["citations"], list)


def test_query_missing_api_key_returns_401(client):
    response = client.post("/query", json={"question": "x"})
    assert response.status_code == 401
