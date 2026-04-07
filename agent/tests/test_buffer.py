import json
import os
import time
import pytest
import responses
from unittest.mock import patch

from agent import save_to_buffer, drain_buffer

BACKEND_URL = "http://localhost:8000"
API_KEY = "test-key"


def make_payload(filename="auth.log"):
    return {
        "source_vm": "vm1-linux",
        "log_type": "intrusion",
        "content": "Failed password for root",
        "filename": filename,
        "ts": "2026-04-07T21:00:00Z",
    }


# --- Saving to buffer ---

def test_failed_batch_saved(tmp_path):
    save_to_buffer(make_payload(), str(tmp_path))
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["source_vm"] == "vm1-linux"


def test_buffer_file_has_all_fields(tmp_path):
    save_to_buffer(make_payload(), str(tmp_path))
    data = json.loads(list(tmp_path.iterdir())[0].read_text())
    for field in ("source_vm", "log_type", "content", "filename", "ts"):
        assert field in data


def test_multiple_failures_create_multiple_files(tmp_path):
    for i in range(3):
        save_to_buffer(make_payload(f"file{i}.log"), str(tmp_path))
        time.sleep(0.01)  # ensure different timestamps
    assert len(list(tmp_path.iterdir())) == 3


def test_buffer_filenames_sortable(tmp_path):
    for i in range(3):
        save_to_buffer(make_payload(f"file{i}.log"), str(tmp_path))
        time.sleep(0.01)
    names = sorted(f.name for f in tmp_path.iterdir())
    # sorted by name should equal sorted by creation time
    assert names == [f.name for f in sorted(tmp_path.iterdir(), key=lambda f: f.name)]


# --- Draining buffer ---

@responses.activate
@patch("time.sleep")
def test_buffered_batch_retried(mock_sleep, tmp_path):
    save_to_buffer(make_payload(), str(tmp_path))
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    drain_buffer(str(tmp_path), BACKEND_URL, API_KEY)
    assert len(list(tmp_path.iterdir())) == 0  # file deleted


@responses.activate
@patch("time.sleep")
def test_drain_oldest_first(mock_sleep, tmp_path):
    for i in range(3):
        save_to_buffer(make_payload(f"file{i}.log"), str(tmp_path))
        time.sleep(0.01)
    for _ in range(3):
        responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    drain_buffer(str(tmp_path), BACKEND_URL, API_KEY)
    bodies = [json.loads(c.request.body)["filename"] for c in responses.calls]
    assert bodies == ["file0.log", "file1.log", "file2.log"]


@responses.activate
@patch("time.sleep")
def test_drain_stops_on_failure(mock_sleep, tmp_path):
    for i in range(3):
        save_to_buffer(make_payload(f"file{i}.log"), str(tmp_path))
        time.sleep(0.01)
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    responses.post(f"{BACKEND_URL}/ingest", json={"error": "fail"}, status=500)
    # need extra 500s for retries
    for _ in range(3):
        responses.post(f"{BACKEND_URL}/ingest", json={"error": "fail"}, status=500)
    drain_buffer(str(tmp_path), BACKEND_URL, API_KEY)
    remaining = list(tmp_path.iterdir())
    assert len(remaining) == 2  # first drained, second+third remain


def test_empty_buffer_noop(tmp_path):
    drain_buffer(str(tmp_path), BACKEND_URL, API_KEY)
    # no error, no calls


@responses.activate
@patch("time.sleep")
def test_buffer_file_kept_on_failure(mock_sleep, tmp_path):
    save_to_buffer(make_payload(), str(tmp_path))
    for _ in range(4):
        responses.post(f"{BACKEND_URL}/ingest", json={"error": "fail"}, status=500)
    drain_buffer(str(tmp_path), BACKEND_URL, API_KEY)
    assert len(list(tmp_path.iterdir())) == 1  # file still there


def test_corrupted_buffer_file_skipped(tmp_path):
    # Write a corrupted JSON file
    bad = tmp_path / "0000_bad.json"
    bad.write_text("{corrupted")
    # Write a valid one after it
    save_to_buffer(make_payload(), str(tmp_path))
    drain_buffer(str(tmp_path), BACKEND_URL, API_KEY)
    # Corrupted file removed, valid file still there (no backend to drain to)
    remaining = list(tmp_path.iterdir())
    assert not any("bad" in f.name for f in remaining)
