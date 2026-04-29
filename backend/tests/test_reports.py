def test_reports_empty_returns_pagination_shape(client, auth_headers):
    response = client.get("/reports", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert isinstance(body["results"], list)


def test_reports_pagination_params_respected(client, auth_headers):
    response = client.get("/reports?page=2&page_size=5", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 2
    assert body["page_size"] == 5


def test_reports_invalid_ts_returns_400(client, auth_headers):
    response = client.get("/reports?from_ts=not-a-date", headers=auth_headers)
    assert response.status_code == 400
