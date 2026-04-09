import json
import pytest

from agent import load_config


@pytest.fixture
def valid_config(tmp_path):
    cfg = {
        "backend_url": "http://localhost:8000",
        "api_key": "test-key",
        "source_vm": "vm1-linux",
        "poll_interval_seconds": 60,
        "log_sources": [
            {"path": "/var/log/auth.log", "log_type": "intrusion"},
            {"path": "/var/log/syslog", "log_type": "http"},
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    return str(p)


def test_load_valid_config(valid_config):
    cfg = load_config(valid_config)
    assert cfg["backend_url"] == "http://localhost:8000"
    assert cfg["api_key"] == "test-key"
    assert cfg["source_vm"] == "vm1-linux"
    assert len(cfg["log_sources"]) == 2


def test_missing_config_file():
    with pytest.raises((FileNotFoundError, SystemExit)):
        load_config("/nonexistent/config.json")


def test_malformed_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{bad json")
    with pytest.raises((json.JSONDecodeError, SystemExit)):
        load_config(str(p))


@pytest.mark.parametrize("missing_field", ["backend_url", "api_key", "source_vm", "log_sources"])
def test_missing_required_field(tmp_path, missing_field):
    cfg = {
        "backend_url": "http://localhost:8000",
        "api_key": "test-key",
        "source_vm": "vm1-linux",
        "poll_interval_seconds": 60,
        "log_sources": [{"path": "/var/log/auth.log", "log_type": "intrusion"}],
    }
    del cfg[missing_field]
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises((KeyError, SystemExit)):
        load_config(str(p))


def test_empty_log_sources(tmp_path):
    cfg = {
        "backend_url": "http://localhost:8000",
        "api_key": "test-key",
        "source_vm": "vm1-linux",
        "poll_interval_seconds": 60,
        "log_sources": [],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    result = load_config(str(p))
    assert result["log_sources"] == []


def test_log_source_missing_path(tmp_path):
    cfg = {
        "backend_url": "http://localhost:8000",
        "api_key": "test-key",
        "source_vm": "vm1-linux",
        "poll_interval_seconds": 60,
        "log_sources": [{"log_type": "intrusion"}],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises((KeyError, SystemExit)):
        load_config(str(p))


def test_log_source_missing_log_type(tmp_path):
    cfg = {
        "backend_url": "http://localhost:8000",
        "api_key": "test-key",
        "source_vm": "vm1-linux",
        "poll_interval_seconds": 60,
        "log_sources": [{"path": "/var/log/auth.log"}],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises((KeyError, SystemExit)):
        load_config(str(p))


def test_invalid_log_type(tmp_path):
    cfg = {
        "backend_url": "http://localhost:8000",
        "api_key": "test-key",
        "source_vm": "vm1-linux",
        "poll_interval_seconds": 60,
        "log_sources": [{"path": "/var/log/auth.log", "log_type": "banana"}],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises((ValueError, SystemExit)):
        load_config(str(p))
