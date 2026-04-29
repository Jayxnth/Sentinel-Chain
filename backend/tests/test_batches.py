def test_batches_empty_returns_pagination_shape(client, auth_headers):
    response = client.get("/batches", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "total" in body
    assert body["total"] == 0
    assert body["results"] == []


def test_batches_after_ingest_lists_the_batch(client, auth_headers):
    payload = {
        "source_vm": "vm-test-batches",
        "log_type": "intrusion",
        "content": "test",
        "filename": "x.log",
        "ts": "2026-04-29T10:00:00Z",
    }
    client.post("/ingest", json=payload, headers=auth_headers)

    response = client.get("/batches", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(b["source_vm"] == "vm-test-batches" for b in body["results"])
