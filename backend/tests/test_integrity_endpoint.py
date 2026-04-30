def test_integrity_empty_returns_empty_dict(client, auth_headers):
    response = client.get("/integrity", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)


def test_integrity_after_ingest_shows_vm(client, auth_headers):
    payload = {
        "source_vm": "vm-integrity-test",
        "log_type": "intrusion",
        "content": "test content",
        "filename": "x.log",
        "ts": "2026-04-29T10:00:00Z",
    }
    client.post("/ingest", json=payload, headers=auth_headers)

    response = client.get("/integrity", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "vm-integrity-test" in body
    vm_status = body["vm-integrity-test"]
    assert vm_status["status"] == "VERIFIED"
    assert "batch_count" in vm_status
    assert "tampered_batch_id" in vm_status
    assert "last_verified_ts" in vm_status


def test_integrity_filtered_by_source_vm(client, auth_headers):
    response = client.get("/integrity?source_vm=nonexistent-vm", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {}
