import io


def test_upload_happy_path(client, auth_headers):
    file_content = b"Failed login from 1.2.3.4"
    files = {"file": ("test.log", io.BytesIO(file_content), "text/plain")}
    data = {"source_vm": "vm-test", "log_type": "intrusion"}
    response = client.post("/upload", files=files, data=data, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "test.log"
    assert body["status"] == "ingested"
    assert isinstance(body["batch_id"], int)
    assert body["integrity_status"] == "VERIFIED"


def test_upload_invalid_log_type_returns_400(client, auth_headers):
    files = {"file": ("test.log", io.BytesIO(b"x"), "text/plain")}
    data = {"source_vm": "vm-test", "log_type": "invalid"}
    response = client.post("/upload", files=files, data=data, headers=auth_headers)
    assert response.status_code == 400


def test_upload_oversized_file_returns_413(client, auth_headers):
    # 11 MB of bytes
    big_content = b"x" * (11 * 1024 * 1024)
    files = {"file": ("big.log", io.BytesIO(big_content), "text/plain")}
    data = {"source_vm": "vm-test", "log_type": "intrusion"}
    response = client.post("/upload", files=files, data=data, headers=auth_headers)
    assert response.status_code == 413
