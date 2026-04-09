# M3 Implementation Plan — Sentinel Agent + Simulator + Tamper Script

**Date:** 2026-04-07 | **Owner:** M3 | **Deadline:** Simulator done by 18 Apr

---

## 1. Deliverables

```
agent/
├── agent.py           # Core agent: config, file reading, offset tracking, HTTP POST, retry/backoff
├── simulator.py       # Continuous log generator with injected attack patterns
├── tamper.py          # DB-level tamper simulation for integrity testing
├── config.json        # Agent configuration
├── requirements.txt   # Agent-specific dependencies
├── sentinel-agent.service   # systemd unit file (Linux / VM1)
└── NSSM-README.md     # Windows Service setup instructions (VM2)
```

---

## 2. Design Decisions (Agreed)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | HTTP client | `requests` (sync) | Agent does one thing at a time. No async complexity needed. |
| 2 | Scheduling | `time.sleep()` loop | Fixed interval, zero dependencies. No need for `schedule` library. |
| 3 | Batch granularity | One POST per file per cycle | Maps cleanly to API contract (one `filename` + `log_type` per batch). |
| 4 | Simulator → Agent | Simulator writes files to disk, agent reads them | Tests full pipeline. More realistic than direct POST. |
| 5 | Simulator mode | Continuous (appends lines every few seconds) | Creates live data flow for demo. Agent picks up new lines each cycle. |
| 6 | Tamper method | Python script, direct DB UPDATE | Server-side hashing means tampering must happen at DB level. |
| 7 | Failed send buffer | Separate JSON files in `buffer/` directory | No corruption risk. Agent retries buffered batches first each cycle. |

---

## 3. API Contract (Assumed)

Based on the agreed async `/ingest` proposal:

```
POST /ingest
Header: X-API-Key: <key>
Content-Type: application/json

Request:
{
  "source_vm": "vm1-linux",
  "log_type": "intrusion",
  "content": "...raw log lines...",
  "filename": "auth.log",
  "ts": "2026-04-07T21:00:00Z"
}

Response (immediate, <1s):
{
  "batch_id": 42,
  "integrity_status": "VERIFIED"
}
```

Status codes: 200 (accepted), 400 (bad request), 401 (bad API key), 500 (not stored), 503 (DB down).

---

## 4. `agent.py` — Detailed Design

### 4.1 Config Loading

Read `config.json` on startup:

```json
{
  "backend_url": "http://10.0.0.4:8000",
  "api_key": "changeme",
  "source_vm": "vm1-linux",
  "poll_interval_seconds": 60,
  "log_sources": [
    {"path": "/var/log/auth.log", "log_type": "intrusion"},
    {"path": "/var/log/apache2/access.log", "log_type": "web"},
    {"path": "/var/log/syslog", "log_type": "http"}
  ]
}
```

Config is loaded once at startup. Agent exits with an error if the file is missing or malformed.

### 4.2 Byte Offset Tracking

State file: `.agent_state.json`

```json
{
  "/var/log/auth.log": {"offset": 12288},
  "/var/log/apache2/access.log": {"offset": 0}
}
```

Per cycle, for each log source:
1. Read current offset from state (default 0 if file is new)
2. Open file, seek to offset
3. Read from offset to EOF
4. If new content exists → build batch, POST to backend
5. On successful POST (200) → update offset to current file position
6. On failure → do NOT update offset (content will be re-read next cycle)
7. Write state file after all sources are processed

Edge cases:
- **File truncated/rotated** (new size < stored offset): reset offset to 0, re-read entire file
- **File deleted**: skip, log warning, keep offset in state for when file reappears
- **File unreadable** (permissions): skip, log warning
- **Corrupted buffer file**: skip, delete the bad file, log warning, continue draining

### 4.3 HTTP POST

For each file with new content:

```python
payload = {
    "source_vm": config["source_vm"],
    "log_type": source["log_type"],
    "content": new_content,
    "filename": os.path.basename(source["path"]),
    "ts": datetime.utcnow().isoformat() + "Z"
}

response = requests.post(
    f"{config['backend_url']}/ingest",
    json=payload,
    headers={"X-API-Key": config["api_key"]},
    timeout=30
)
```

### 4.4 Retry with Exponential Backoff

On POST failure (network error, timeout, 5xx):
1. Retry up to 3 times with delays: 2s, 4s, 8s
2. If all retries fail → save batch to `buffer/` directory as a JSON file
3. Log the failure

On 400 (bad request) or 401 (bad key): do NOT retry (client error, won't fix itself). Log and skip.

### 4.5 Buffer Drain

At the start of each cycle, before reading new content:
1. Check `buffer/` directory for any `.json` files
2. For each file (oldest first by filename timestamp):
   - Read the payload
   - POST to backend
   - On success → delete the buffer file
   - On failure → stop draining (backend still down), proceed to normal cycle

Buffer filename format: `buffer/{unix_timestamp}_{filename}.json`

### 4.6 Main Loop

```
startup:
  load config
  load state

loop:
  drain buffer (retry previously failed batches)
  for each log_source in config:
    read new content since last offset
    if new content:
      POST to /ingest (with retry)
      if success: update offset
      if failure: save to buffer
  save state
  sleep(poll_interval_seconds)
```

Graceful shutdown on SIGTERM/SIGINT (for systemd compatibility).

---

## 5. `simulator.py` — Detailed Design

### 5.1 Purpose

Runs continuously alongside the agent. Appends realistic log lines (including attack patterns) to the same files the agent is configured to read. The agent picks them up naturally each cycle.

### 5.2 Output Paths

The simulator writes to a configurable output directory (default: `/var/log/sentinel-sim/` on Linux, `C:\sentinel-sim\logs\` on Windows). The agent's `config.json` points to these paths. The hostname used in generated log lines is configurable via `--hostname` (default: `vm1-linux`).

### 5.3 Log Formats

Four log types, each with a realistic format:

**intrusion** (auth.log style — syslog format):
```
Apr  7 14:23:01 vm1-linux sshd[1234]: Accepted password for admin from 10.0.0.1 port 22 ssh2
Apr  7 14:23:05 vm1-linux sshd[1235]: Failed password for root from 192.168.1.100 port 22 ssh2
```

**web** (Apache access log format):
```
192.168.1.50 - - [07/Apr/2026:14:23:01 +0000] "GET /index.html HTTP/1.1" 200 1234
192.168.1.100 - - [07/Apr/2026:14:23:02 +0000] "GET /search?q=1'+OR+'1'='1 HTTP/1.1" 400 0
```

**malware** (syslog with process/file indicators):
```
Apr  7 14:23:01 vm1-linux kernel: [UFW BLOCK] IN=eth0 SRC=203.0.113.50 DST=10.0.0.2 PROTO=TCP DPT=4444
Apr  7 14:23:02 vm1-linux clamd[5678]: /tmp/.hidden/payload.exe: Win.Trojan.Agent FOUND
```

**http** (HTTP request log):
```
2026-04-07T14:23:01Z GET /api/users 200 12ms 10.0.0.1
2026-04-07T14:23:02Z POST /api/login 401 3ms 192.168.1.100
```

### 5.4 Attack Patterns

Each log type has a pool of normal lines and attack lines. The simulator:
- Appends 5–15 normal lines per interval
- With 30% probability, injects 3–8 attack lines into the batch

Attack templates per type:

| log_type   | Attack Pattern | Example |
|------------|---------------|---------|
| intrusion  | SSH brute force | 20+ failed password attempts from same IP in <1 min |
| intrusion  | Privilege escalation | sudo attempts by unauthorized user |
| web        | SQL injection | `' OR '1'='1`, `UNION SELECT`, `DROP TABLE` in query params |
| web        | Path traversal | `../../etc/passwd` in URL |
| malware    | Reverse shell | Outbound connection on port 4444/4445 |
| malware    | Suspicious binary | Known malware filenames detected by AV |
| http       | Credential stuffing | Rapid 401s on /login from single IP |
| http       | API abuse | Excessive requests to sensitive endpoints |

### 5.5 Main Loop

```
startup:
  create output directories if needed

loop:
  for each log_type:
    generate 5-15 normal lines
    if random() < 0.3: inject 3-8 attack lines
    append all lines to the corresponding log file
  sleep(5-10 seconds, randomized)
```

The simulator runs independently of the agent. It just writes files. The agent reads them on its own schedule.

---

## 6. `tamper.py` — Detailed Design

### 6.1 Purpose

Connects to the PostgreSQL database on VM3 and modifies stored batch content to simulate post-storage tampering. This triggers `verify_chain()` to return `TAMPERED`.

### 6.2 Usage

```bash
# Tamper a specific batch
python tamper.py --db-url postgresql://user:pass@10.0.0.4:5432/sentinel --batch-id 42

# Tamper a random batch for a given VM
python tamper.py --db-url postgresql://user:pass@10.0.0.4:5432/sentinel --source-vm vm1-linux
```

### 6.3 What It Does

1. Connect to PostgreSQL
2. Select the target batch (by ID or random for a given source_vm)
3. Modify the `content` column (append a line like `[TAMPERED BY TEST SCRIPT]` or delete a random line)
4. Commit the UPDATE
5. Print confirmation: "Tampered batch {id} for {source_vm}. verify_chain() should now return TAMPERED."

This is intentionally simple — it's a test tool, not production code.

### 6.4 Dependency

Requires direct DB access to VM3's PostgreSQL. This script is meant to be run by M5 on VM3, or remotely if the DB port is reachable. It will NOT work with SQLite during local development — for local testing, a SQLite variant can be added.

---

## 7. `requirements.txt`

```
requests
```

That's it. The agent is intentionally lightweight — no LangChain, no ChromaDB, no ML dependencies. `tamper.py` additionally needs `psycopg2-binary` but that's only installed on the machine running the tamper script, not on the agent VMs.

---

## 8. Deployment

### 8.1 Linux (VM1) — systemd

Service file `sentinel-agent.service`:
- Runs `python3 agent.py` as a daemon
- `Restart=always` with `RestartSec=5` for crash recovery
- `WorkingDirectory` set to the agent directory
- Logs to journald (`journalctl -u sentinel-agent`)

Install: `sudo cp sentinel-agent.service /etc/systemd/system/ && sudo systemctl enable --now sentinel-agent`

Simulator runs as a separate service `sentinel-simulator.service` with the same pattern.

### 8.2 Windows (VM2) — NSSM

NSSM wraps any executable as a Windows Service:
```
nssm install SentinelAgent "C:\Python311\python.exe" "C:\sentinel\agent.py"
nssm set SentinelAgent AppDirectory "C:\sentinel"
nssm start SentinelAgent
```

Same for the simulator. Instructions documented in `NSSM-README.md`.

---

## 9. Testing Strategy

### 9.1 Local Development (no VM needed)

1. Run the mock backend (simple FastAPI with `/ingest` and `/health`)
2. Run `simulator.py` → generates log files in a local directory
3. Run `agent.py` with config pointing to local files and `http://localhost:8000`
4. Verify: agent reads files, tracks offsets, POSTs batches, handles retries

### 9.2 Integration (Week 3–4, needs M2 backend on VM3)

1. Deploy agent + simulator on VM1
2. Point config to VM3's real `/ingest` endpoint
3. Verify batches appear in PostgreSQL and ChromaDB
4. Run `tamper.py` on VM3 → verify dashboard shows TAMPERED badge

### 9.3 Edge Cases to Test

- Agent starts with no log files → no POSTs, no errors
- Log file rotated mid-cycle → offset reset, re-read from 0
- Backend down → batches buffered, retried next cycle
- Backend returns 401 → logged, not retried
- Simultaneous agents (VM1 + VM2) sending to same backend → no race conditions (M2's responsibility, but verify)

---

## 10. Timeline (per implementation plan)

| Week | Deliverable |
|------|-------------|
| Week 1 (done) | Agree log format with M2 ✓ |
| Week 2 (this week) | `agent.py` core + `simulator.py` Linux version + local testing |
| Week 3 | Windows simulator on VM2 + NSSM service + both VMs sending live |
| Week 4 | `tamper.py` + E2E integration tests + tamper detection verified on dashboard |
