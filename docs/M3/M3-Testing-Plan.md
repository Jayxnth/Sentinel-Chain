# M3 Testing Plan (TDD)

**Date:** 2026-04-07 | **Framework:** pytest | **Approach:** Write tests first, then implement to pass them

---

## 1. Test Structure

```
agent/
├── tests/
│   ├── conftest.py              # Shared fixtures (tmp dirs, mock config, mock server responses)
│   ├── test_config.py           # Config loading
│   ├── test_offset.py           # Byte offset tracking + state persistence
│   ├── test_sender.py           # HTTP POST + retry/backoff
│   ├── test_buffer.py           # Local buffer save/drain
│   ├── test_agent_loop.py       # Main loop integration
│   ├── test_simulator.py        # Log generation + attack injection
│   └── test_tamper.py           # DB tamper script
```

---

## 2. Mocking Strategy

| Dependency | Mock Method |
|---|---|
| HTTP calls to backend | `responses` library (intercepts `requests.post`) |
| File system (log files, state, buffer) | pytest `tmp_path` fixture — real files in temp directories |
| Database (tamper.py) | SQLite in-memory via SQLAlchemy (same models as M2) |
| Time/sleep | `unittest.mock.patch("time.sleep")` to skip waits in tests |

---

## 3. Test Dependencies

```
pytest
responses
```

---

## 4. `test_config.py` — Config Loading

| # | Test | Expected |
|---|------|----------|
| 1 | Load valid `config.json` with all fields | Returns config dict with correct values |
| 2 | Config file missing | Raises `FileNotFoundError` or `SystemExit` |
| 3 | Config file is malformed JSON | Raises `json.JSONDecodeError` or `SystemExit` |
| 4 | Config missing `backend_url` | Raises `KeyError` or `SystemExit` |
| 5 | Config missing `api_key` | Raises `KeyError` or `SystemExit` |
| 6 | Config missing `source_vm` | Raises `KeyError` or `SystemExit` |
| 7 | Config missing `log_sources` | Raises `KeyError` or `SystemExit` |
| 8 | Config `log_sources` is empty array | Loads successfully (no sources to monitor is valid) |
| 9 | Config `log_sources` entry missing `path` | Raises error |
| 10 | Config `log_sources` entry missing `log_type` | Raises error |
| 11 | Config `log_type` not in `["malware", "intrusion", "web", "http"]` | Raises error |

---

## 5. `test_offset.py` — Byte Offset Tracking

### Reading new content

| # | Test | Setup | Expected |
|---|------|-------|----------|
| 1 | New file, no prior state | Create file with 100 bytes, no state entry | Returns all 100 bytes, offset = 100 |
| 2 | File with prior offset | File has 200 bytes, state says offset=100 | Returns bytes 100–200 only |
| 3 | No new content | File has 100 bytes, state says offset=100 | Returns empty string |
| 4 | File truncated (rotated) | File has 50 bytes, state says offset=200 | Resets offset to 0, returns all 50 bytes |
| 5 | File does not exist | State has entry but file is gone | Returns None, logs warning |
| 6 | File unreadable (permissions) | File exists but no read permission | Returns None, logs warning |
| 7 | Empty file | File exists but is 0 bytes | Returns empty string |

### State persistence

| # | Test | Setup | Expected |
|---|------|-------|----------|
| 8 | State saved after cycle | Process two files | State file contains both offsets |
| 9 | State loaded on restart | Write state file, create new reader | Offsets match saved values |
| 10 | State file missing on first run | No state file exists | All offsets default to 0 |
| 11 | State file corrupted | Write invalid JSON to state file | All offsets default to 0, log warning |
| 12 | Offset only updated on success | POST fails for one file | That file's offset unchanged, other file's offset updated |

---

## 6. `test_sender.py` — HTTP POST + Retry/Backoff

### Successful sends

| # | Test | Mock | Expected |
|---|------|------|----------|
| 1 | Successful POST | Mock 200 `{"batch_id": 1, "integrity_status": "VERIFIED"}` | Returns response, no retry |
| 2 | Request body is correct | Mock 200, capture request | Body has `source_vm`, `log_type`, `content`, `filename`, `ts` |
| 3 | API key header sent | Mock 200, capture request | `X-API-Key` header present with correct value |
| 4 | `ts` is valid ISO 8601 | Mock 200, capture request | `ts` field parses as datetime |

### Client errors (no retry)

| # | Test | Mock | Expected |
|---|------|------|----------|
| 5 | 400 bad request | Mock 400 | Returns failure, no retry attempted |
| 6 | 401 unauthorized | Mock 401 | Returns failure, no retry attempted |

### Server errors (retry with backoff)

| # | Test | Mock | Expected |
|---|------|------|----------|
| 7 | 500 then 200 | Mock 500 once, then 200 | Retries once, succeeds on second attempt |
| 8 | 500 three times then 200 | Mock 500 ×3, then 200 | Retries 3 times, succeeds on fourth attempt |
| 9 | 500 four times (all retries exhausted) | Mock 500 ×4 | Returns failure after 3 retries |
| 10 | 503 triggers retry | Mock 503 once, then 200 | Retries, succeeds |

### Network errors (retry with backoff)

| # | Test | Mock | Expected |
|---|------|------|----------|
| 11 | Connection timeout | Mock `requests.exceptions.Timeout` then 200 | Retries, succeeds |
| 12 | Connection refused | Mock `requests.exceptions.ConnectionError` then 200 | Retries, succeeds |
| 13 | All retries fail on network error | Mock `ConnectionError` ×4 | Returns failure after 3 retries |

### Backoff timing

| # | Test | Mock | Expected |
|---|------|------|----------|
| 14 | Backoff delays are 2s, 4s, 8s | Mock 500 ×3, patch `time.sleep` | `sleep` called with 2, 4, 8 |

---

## 7. `test_buffer.py` — Local Buffer

### Saving to buffer

| # | Test | Setup | Expected |
|---|------|-------|----------|
| 1 | Failed batch saved to buffer | Trigger a send failure | JSON file created in `buffer/` with correct payload |
| 2 | Buffer file contains all fields | Save a batch | File has `source_vm`, `log_type`, `content`, `filename`, `ts` |
| 3 | Multiple failures create multiple files | Fail 3 batches | 3 separate files in `buffer/` |
| 4 | Buffer filenames are sortable by time | Save 3 batches with small delays | Filenames sort in creation order |

### Draining buffer

| # | Test | Setup | Expected |
|---|------|-------|----------|
| 5 | Buffered batch retried on next cycle | Save 1 batch, mock 200 | Batch POSTed, buffer file deleted |
| 6 | Multiple buffered batches drained oldest first | Save 3 batches, mock 200 | POSTed in chronological order |
| 7 | Drain stops on failure | Save 3 batches, mock 200 then 500 | First batch drained, second fails, third not attempted |
| 8 | Empty buffer is no-op | No files in `buffer/` | No POSTs made during drain phase |
| 9 | Buffer file deleted only on 200 | Save 1 batch, mock 500 | File still exists in `buffer/` |
| 10 | Corrupted buffer file skipped and removed | Write invalid JSON to buffer, then a valid file | Corrupted file deleted, valid file untouched |

---

## 8. `test_agent_loop.py` — Main Loop Integration

| # | Test | Setup | Expected |
|---|------|-------|----------|
| 1 | Full cycle: read → POST → update offset | File with content, mock 200 | Content POSTed, offset updated, state saved |
| 2 | Cycle with no new content | File unchanged since last cycle | No POST made |
| 3 | Cycle drains buffer before reading files | 1 buffered batch + 1 file with new content, mock 200 | Buffer drained first, then file content POSTed |
| 4 | Multiple files in one cycle | 3 files with new content, mock 200 | 3 separate POSTs made |
| 5 | Partial failure in cycle | 2 files, first POST 200, second POST 500 | First offset updated, second offset unchanged, second batch buffered |
| 6 | Graceful shutdown on SIGTERM | Send SIGTERM during sleep | Loop exits cleanly, state saved |

---

## 9. `test_simulator.py` — Log Generation

### Format validation

| # | Test | Expected |
|---|------|----------|
| 1 | Intrusion lines match syslog format | Each line matches regex: `^[A-Z][a-z]{2}\s+\d+\s\d{2}:\d{2}:\d{2}\s\S+\s\S+:.*` |
| 2 | Web lines match Apache access log format | Each line matches regex: `^\S+\s-\s-\s\[.+\]\s".+"\s\d{3}\s\d+` |
| 3 | Malware lines match syslog format | Same syslog regex as intrusion |
| 4 | HTTP lines match request log format | Each line matches regex: `^\d{4}-\d{2}-\d{2}T.+\s(GET\|POST\|PUT\|DELETE)\s\S+\s\d{3}` |

### Attack injection

| # | Test | Expected |
|---|------|----------|
| 5 | SSH brute force pattern | Generated lines contain multiple "Failed password" from same IP |
| 6 | SQL injection pattern | Generated lines contain SQL keywords (`OR '1'='1`, `UNION SELECT`, etc.) |
| 7 | Path traversal pattern | Generated lines contain `../` sequences |
| 8 | Reverse shell pattern | Generated lines contain outbound connection on port 4444 or 4445 |
| 9 | Credential stuffing pattern | Generated lines contain rapid 401 responses from same IP |
| 10 | Malware detection pattern | Generated lines contain known malware indicators |

### File writing

| # | Test | Expected |
|---|------|----------|
| 11 | Appends to existing file | File had 10 lines, after write has >10 lines |
| 12 | Creates file if missing | File doesn't exist → created with content |
| 13 | Creates directory if missing | Directory doesn't exist → created, file written |

### Mix ratio

| # | Test | Expected |
|---|------|----------|
| 14 | Normal lines generated every cycle | At least 5 lines per log type per cycle |
| 15 | Attack lines injected in ~30% of cycles | Over 100 cycles, attack injection count is between 15–45 |

---

## 10. `test_tamper.py` — DB Tamper Script

| # | Test | Setup | Expected |
|---|------|-------|----------|
| 1 | Tampers specified batch | Insert 3 batches into SQLite in-memory DB | Batch content modified, differs from original |
| 2 | Tampers random batch for source_vm | Insert 5 batches for "vm1-linux" | One batch's content modified |
| 3 | Invalid batch_id | No batch with ID 999 | Prints error, exits cleanly |
| 4 | DB connection failure | Invalid connection string | Prints error, exits cleanly |
| 5 | Tampered batch detected by verify_chain | Insert 3 batches with valid chain, tamper batch 2 | `verify_chain()` returns `TAMPERED` with `tampered_batch_id=2` |
| 6 | `batch_id=0` treated as valid ID | Insert batch with id=0 scenario | Not skipped by falsy check |

Test 5 is the end-to-end proof: tamper.py breaks the chain → M2's `verify_chain()` catches it.

---

## 11. TDD Implementation Order

Tests are written and run (failing) before the corresponding implementation. Order follows dependency chain:

| Step | Write Tests | Then Implement |
|------|-------------|----------------|
| 1 | `test_config.py` | Config loading in `agent.py` |
| 2 | `test_offset.py` | Byte offset reader + state persistence |
| 3 | `test_sender.py` | HTTP POST + retry/backoff |
| 4 | `test_buffer.py` | Buffer save/drain |
| 5 | `test_agent_loop.py` | Main loop wiring |
| 6 | `test_simulator.py` | Log generation + attack patterns + file writing |
| 7 | `test_tamper.py` | DB tamper script |

Each step: write all tests for that module → run (all red) → implement → run (all green) → next step.
