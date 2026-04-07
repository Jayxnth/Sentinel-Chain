import json
import os
import pytest
import responses
import signal
from unittest.mock import patch

from agent import run_cycle, load_config

BACKEND_URL = "http://localhost:8000"
API_KEY = "test-key"


def write_config(tmp_path, log_sources):
    cfg = {
        "backend_url": BACKEND_URL,
        "api_key": API_KEY,
        "source_vm": "vm1-linux",
        "poll_interval_seconds": 1,
        "log_sources": log_sources,
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    return load_config(str(p))


@responses.activate
def test_full_cycle(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("line1\nline2\n")
    cfg = write_config(tmp_path, [{"path": str(log), "log_type": "intrusion"}])
    state_path = str(tmp_path / ".agent_state.json")
    buffer_dir = str(tmp_path / "buffer")

    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)

    state = run_cycle(cfg, state_path, buffer_dir)

    assert len(responses.calls) == 1
    body = json.loads(responses.calls[0].request.body)
    assert body["content"] == "line1\nline2\n"
    assert state[str(log)]["offset"] == len("line1\nline2\n")


@responses.activate
def test_no_new_content_no_post(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("line1\n")
    cfg = write_config(tmp_path, [{"path": str(log), "log_type": "intrusion"}])
    state_path = str(tmp_path / ".agent_state.json")
    buffer_dir = str(tmp_path / "buffer")

    # First cycle reads everything
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    state = run_cycle(cfg, state_path, buffer_dir)

    # Second cycle — no new content
    state = run_cycle(cfg, state_path, buffer_dir)
    assert len(responses.calls) == 1  # no second POST


@responses.activate
def test_drains_buffer_before_files(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("new content\n")
    cfg = write_config(tmp_path, [{"path": str(log), "log_type": "intrusion"}])
    state_path = str(tmp_path / ".agent_state.json")
    buffer_dir = str(tmp_path / "buffer")

    # Pre-populate buffer
    os.makedirs(buffer_dir)
    buffered = {"source_vm": "vm1-linux", "log_type": "intrusion", "content": "buffered", "filename": "old.log", "ts": "2026-04-07T20:00:00Z"}
    with open(os.path.join(buffer_dir, "0000_old.log.json"), "w") as f:
        json.dump(buffered, f)

    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 2, "integrity_status": "VERIFIED"}, status=200)

    run_cycle(cfg, state_path, buffer_dir)

    assert len(responses.calls) == 2
    first_body = json.loads(responses.calls[0].request.body)
    assert first_body["content"] == "buffered"  # buffer drained first


@responses.activate
def test_multiple_files_in_one_cycle(tmp_path):
    log1 = tmp_path / "auth.log"
    log2 = tmp_path / "access.log"
    log1.write_text("auth line\n")
    log2.write_text("web line\n")
    cfg = write_config(tmp_path, [
        {"path": str(log1), "log_type": "intrusion"},
        {"path": str(log2), "log_type": "web"},
    ])
    state_path = str(tmp_path / ".agent_state.json")
    buffer_dir = str(tmp_path / "buffer")

    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 2, "integrity_status": "VERIFIED"}, status=200)

    run_cycle(cfg, state_path, buffer_dir)
    assert len(responses.calls) == 2


@responses.activate
@patch("time.sleep")
def test_partial_failure(mock_sleep, tmp_path):
    log1 = tmp_path / "auth.log"
    log2 = tmp_path / "access.log"
    log1.write_text("auth line\n")
    log2.write_text("web line\n")
    cfg = write_config(tmp_path, [
        {"path": str(log1), "log_type": "intrusion"},
        {"path": str(log2), "log_type": "web"},
    ])
    state_path = str(tmp_path / ".agent_state.json")
    buffer_dir = str(tmp_path / "buffer")

    # First POST succeeds, second fails all retries
    responses.post(f"{BACKEND_URL}/ingest", json={"batch_id": 1, "integrity_status": "VERIFIED"}, status=200)
    for _ in range(4):
        responses.post(f"{BACKEND_URL}/ingest", json={"error": "fail"}, status=500)

    state = run_cycle(cfg, state_path, buffer_dir)

    # First file offset updated, second unchanged
    assert state[str(log1)]["offset"] == len("auth line\n")
    assert str(log2) not in state
    # Second batch buffered
    assert len(os.listdir(buffer_dir)) == 1
