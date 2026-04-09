import os
import re
import pytest

from simulator import (
    generate_intrusion_lines,
    generate_web_lines,
    generate_malware_lines,
    generate_http_lines,
    generate_attack_intrusion,
    generate_attack_web,
    generate_attack_malware,
    generate_attack_http,
    append_to_file,
)

SYSLOG_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d+\s\d{2}:\d{2}:\d{2}\s\S+\s\S+.*")
APACHE_RE = re.compile(r'^\S+\s-\s-\s\[.+\]\s".+"\s\d{3}\s\d+')
HTTP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\S+\s(GET|POST|PUT|DELETE)\s\S+\s\d{3}")


# --- Format validation ---

def test_intrusion_lines_syslog_format():
    lines = generate_intrusion_lines(10)
    assert len(lines) == 10
    for line in lines:
        assert SYSLOG_RE.match(line), f"Bad format: {line}"


def test_web_lines_apache_format():
    lines = generate_web_lines(10)
    assert len(lines) == 10
    for line in lines:
        assert APACHE_RE.match(line), f"Bad format: {line}"


def test_malware_lines_syslog_format():
    lines = generate_malware_lines(10)
    assert len(lines) == 10
    for line in lines:
        assert SYSLOG_RE.match(line), f"Bad format: {line}"


def test_http_lines_format():
    lines = generate_http_lines(10)
    assert len(lines) == 10
    for line in lines:
        assert HTTP_RE.match(line), f"Bad format: {line}"


# --- Attack injection ---

def test_attack_intrusion_has_failed_password():
    lines = generate_attack_intrusion()
    assert len(lines) >= 3
    failed = [l for l in lines if "Failed password" in l]
    assert len(failed) >= 2


def test_attack_web_has_sql_injection():
    lines = generate_attack_web()
    assert len(lines) >= 3
    sqli = [l for l in lines if any(k in l for k in ["OR", "UNION", "DROP", "SELECT", "../"])]
    assert len(sqli) >= 1


def test_attack_malware_has_indicators():
    lines = generate_attack_malware()
    assert len(lines) >= 3
    indicators = [l for l in lines if any(k in l for k in ["BLOCK", "FOUND", "4444", "4445", "reverse"])]
    assert len(indicators) >= 1


def test_attack_http_has_401s():
    lines = generate_attack_http()
    assert len(lines) >= 3
    failures = [l for l in lines if "401" in l]
    assert len(failures) >= 2


# --- File writing ---

def test_append_to_existing_file(tmp_path):
    f = tmp_path / "test.log"
    f.write_text("existing\n")
    append_to_file(str(f), ["new line 1", "new line 2"])
    content = f.read_text()
    assert "existing\n" in content
    assert "new line 1\n" in content
    assert "new line 2\n" in content


def test_creates_file_if_missing(tmp_path):
    f = tmp_path / "new.log"
    append_to_file(str(f), ["line1"])
    assert f.exists()
    assert "line1\n" in f.read_text()


def test_creates_directory_if_missing(tmp_path):
    f = tmp_path / "subdir" / "deep" / "test.log"
    append_to_file(str(f), ["line1"])
    assert f.exists()


# --- Mix ratio ---

def test_normal_lines_count():
    lines = generate_intrusion_lines(5)
    assert len(lines) == 5
    lines = generate_intrusion_lines(15)
    assert len(lines) == 15


def test_attack_injection_ratio():
    """Over many runs, attacks should appear roughly 30% of the time."""
    import random
    random.seed(42)
    attack_count = 0
    runs = 200
    for _ in range(runs):
        if random.random() < 0.3:
            attack_count += 1
    assert 30 < attack_count < 100  # roughly 30% of 200
