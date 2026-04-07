import json
import os
import pytest

from agent import read_new_content, load_state, save_state


@pytest.fixture
def state_path(tmp_path):
    return str(tmp_path / ".agent_state.json")


# --- Reading new content ---

def test_new_file_no_prior_state(tmp_path, state_path):
    log = tmp_path / "auth.log"
    log.write_text("line1\nline2\n")
    state = {}
    content, new_offset = read_new_content(str(log), state)
    assert content == "line1\nline2\n"
    assert new_offset == len("line1\nline2\n")


def test_reads_from_stored_offset(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("old\nnew\n")
    state = {str(log): {"offset": 4}}
    content, new_offset = read_new_content(str(log), state)
    assert content == "new\n"
    assert new_offset == 8


def test_no_new_content(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("line1\n")
    state = {str(log): {"offset": 6}}
    content, new_offset = read_new_content(str(log), state)
    assert content == ""
    assert new_offset == 6


def test_file_truncated_resets_offset(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("short\n")
    state = {str(log): {"offset": 999}}
    content, new_offset = read_new_content(str(log), state)
    assert content == "short\n"
    assert new_offset == 6


def test_file_does_not_exist():
    state = {}
    content, new_offset = read_new_content("/nonexistent/file.log", state)
    assert content is None
    assert new_offset is None


def test_empty_file(tmp_path):
    log = tmp_path / "auth.log"
    log.write_text("")
    state = {}
    content, new_offset = read_new_content(str(log), state)
    assert content == ""
    assert new_offset == 0


# --- State persistence ---

def test_save_and_load_state(state_path):
    state = {"/var/log/auth.log": {"offset": 100}, "/var/log/syslog": {"offset": 200}}
    save_state(state, state_path)
    loaded = load_state(state_path)
    assert loaded == state


def test_load_state_missing_file(state_path):
    loaded = load_state(state_path)
    assert loaded == {}


def test_load_state_corrupted_file(state_path):
    with open(state_path, "w") as f:
        f.write("{bad json")
    loaded = load_state(state_path)
    assert loaded == {}


def test_offset_only_updated_on_success(tmp_path, state_path):
    """Offset should not change if we just read — caller decides when to update."""
    log = tmp_path / "auth.log"
    log.write_text("line1\nline2\n")
    state = {}
    content, new_offset = read_new_content(str(log), state)
    # State dict should NOT be mutated by read_new_content
    assert str(log) not in state
    # Caller updates state only after successful POST
    state[str(log)] = {"offset": new_offset}
    assert state[str(log)]["offset"] == len("line1\nline2\n")
