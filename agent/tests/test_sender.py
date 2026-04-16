import json
import pytest
import responses
from unittest.mock import patch

from agent import send_batch

BACKEND_URL = "http://localhost:8000"
API_KEY = "test-key"


def make_payload():
    return {
        "source_vm": "vm1-linux",
        "log_type": "intrusion",
        "content": "Failed password for root from 192.168.1.100 port 22 ssh2",
        "filename": "auth.log",
        "ts": "2026-04-07T21:00:00Z",
    }


# --- Successful sends ---

@responses.activate
def test_successful_post():
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is True
    assert result["batch_id"] == 1


@responses.activate
def test_request_body_correct():
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    payload = make_payload()
    send_batch(payload, BACKEND_URL, API_KEY)
    body = json.loads(responses.calls[0].request.body)
    assert body["source_vm"] == "vm1-linux"
    assert body["log_type"] == "intrusion"
    assert body["content"] == payload["content"]
    assert body["filename"] == "auth.log"
    assert "ts" in body


@responses.activate
def test_api_key_header_sent():
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert responses.calls[0].request.headers["X-API-Key"] == API_KEY


# --- Client errors (no retry) ---

@responses.activate
def test_400_no_retry():
    responses.post(f"{BACKEND_URL}/ingest", json={"error": "bad request"}, status=400)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is False
    assert len(responses.calls) == 1


@responses.activate
def test_401_no_retry():
    responses.post(f"{BACKEND_URL}/ingest", json={"error": "unauthorized"}, status=401)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is False
    assert len(responses.calls) == 1


# --- Server errors (retry with backoff) ---

@responses.activate
@patch("time.sleep")
def test_500_then_200(mock_sleep):
    responses.post(f"{BACKEND_URL}/ingest", json={"error": "internal"}, status=500)
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is True
    assert len(responses.calls) == 2


@responses.activate
@patch("time.sleep")
def test_500_three_times_then_200(mock_sleep):
    for _ in range(3):
        responses.post(f"{BACKEND_URL}/ingest", json={"error": "internal"}, status=500)
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is True
    assert len(responses.calls) == 4


@responses.activate
@patch("time.sleep")
def test_all_retries_exhausted(mock_sleep):
    for _ in range(4):
        responses.post(f"{BACKEND_URL}/ingest", json={"error": "internal"}, status=500)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is False
    assert len(responses.calls) == 4  # 1 initial + 3 retries


@responses.activate
@patch("time.sleep")
def test_503_triggers_retry(mock_sleep):
    responses.post(f"{BACKEND_URL}/ingest", json={"error": "unavailable"}, status=503)
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is True
    assert len(responses.calls) == 2


# --- Network errors (retry with backoff) ---

@responses.activate
@patch("time.sleep")
def test_timeout_then_200(mock_sleep):
    import requests as req
    responses.post(f"{BACKEND_URL}/ingest", body=req.exceptions.Timeout())
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is True
    assert len(responses.calls) == 2


@responses.activate
@patch("time.sleep")
def test_connection_error_then_200(mock_sleep):
    import requests as req
    responses.post(f"{BACKEND_URL}/ingest", body=req.exceptions.ConnectionError())
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is True
    assert len(responses.calls) == 2


@responses.activate
@patch("time.sleep")
def test_all_network_retries_fail(mock_sleep):
    import requests as req
    for _ in range(4):
        responses.post(f"{BACKEND_URL}/ingest", body=req.exceptions.ConnectionError())
    result = send_batch(make_payload(), BACKEND_URL, API_KEY)
    assert result["success"] is False
    assert len(responses.calls) == 4


# --- Backoff timing ---

@responses.activate
@patch("time.sleep")
def test_backoff_delays(mock_sleep):
    for _ in range(3):
        responses.post(f"{BACKEND_URL}/ingest", json={"error": "internal"}, status=500)
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    send_batch(make_payload(), BACKEND_URL, API_KEY)
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [2, 4, 8]
