import pytest


PROTECTED_ENDPOINTS = [
    ("GET", "/batches"),
    ("GET", "/reports"),
    ("GET", "/integrity"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_missing_api_key_returns_401(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
def test_wrong_api_key_returns_401(client, method, path):
    response = client.request(method, path, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_correct_api_key_returns_200(client, auth_headers):
    response = client.get("/batches", headers=auth_headers)
    assert response.status_code == 200
