def test_ingest_happy_path(client, auth_headers):
    payload = {
        "source_vm": "vm-test",
        "log_type": "intrusion",
        "content": "Failed login from 1.2.3.4",
        "filename": "auth.log",
        "ts": "2026-04-29T10:00:00Z",
    }
    response = client.post("/ingest", json=payload, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["batch_id"], int)
    assert body["integrity_status"] == "VERIFIED"


def test_ingest_invalid_log_type_returns_400(client, auth_headers):
    payload = {
        "source_vm": "vm-test",
        "log_type": "invalid",
        "content": "x",
        "filename": "x.log",
        "ts": "2026-04-29T10:00:00Z",
    }
    response = client.post("/ingest", json=payload, headers=auth_headers)
    assert response.status_code == 400


def test_ingest_invalid_ts_returns_400(client, auth_headers):
    payload = {
        "source_vm": "vm-test",
        "log_type": "intrusion",
        "content": "x",
        "filename": "x.log",
        "ts": "not-a-timestamp",
    }
    response = client.post("/ingest", json=payload, headers=auth_headers)
    assert response.status_code == 400


def test_ingest_missing_api_key_returns_401(client):
    payload = {
        "source_vm": "vm-test",
        "log_type": "intrusion",
        "content": "x",
        "filename": "x.log",
        "ts": "2026-04-29T10:00:00Z",
    }
    response = client.post("/ingest", json=payload)
    assert response.status_code == 401
