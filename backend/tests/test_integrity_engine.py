import pytest
from backend.integrity import compute_hash, verify_chain


def test_compute_hash_deterministic():
    h1 = compute_hash("some content", "0" * 64)
    h2 = compute_hash("some content", "0" * 64)
    assert h1 == h2
    assert len(h1) == 64


def test_compute_hash_changes_with_content():
    h1 = compute_hash("content A", "0" * 64)
    h2 = compute_hash("content B", "0" * 64)
    assert h1 != h2


def test_compute_hash_changes_with_prev_hash():
    h1 = compute_hash("same content", "0" * 64)
    h2 = compute_hash("same content", "1" * 64)
    assert h1 != h2
