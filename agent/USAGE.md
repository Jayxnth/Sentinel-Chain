# M3 Agent — Usage & Demo Guide

## Prerequisites

- Python 3.11+
- `pip install requests` (agent) and `pip install fastapi uvicorn` (mock backend for local demo)

---

## 1. Local Demo (No VM or Backend Needed)

### Step 1: Use the demo config

```bash
cp config.demo.json config.json
```

### Step 2: Start the mock backend (Terminal 1)

```bash
cd agent/
python mock_backend.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Start the simulator (Terminal 2)

```bash
cd agent/
python simulator.py --output-dir ./sim_logs --interval 3
```

You should see:
```
2026-04-07 22:00:01 [INFO] Simulator started, writing to ./sim_logs
2026-04-07 22:00:04 [INFO] Injected attack into intrusion
2026-04-07 22:00:07 [INFO] Injected attack into web
```

### Step 4: Start the agent (Terminal 3)

```bash
cd agent/
python agent.py
```

You should see:
```
2026-04-07 22:00:10 [INFO] Sentinel Agent started (source_vm=vm1-linux, interval=10s)
```

And in Terminal 1 (mock backend):
```
Batch #1 from vm1-linux (intrusion) — 847 bytes — VERIFIED
Batch #2 from vm1-linux (web) — 623 bytes — VERIFIED
Batch #3 from vm1-linux (malware) — 512 bytes — VERIFIED
Batch #4 from vm1-linux (http) — 391 bytes — VERIFIED
```

### What's Happening

1. Simulator appends 5–15 log lines per type every ~3 seconds
2. ~30% of cycles include injected attack patterns (SSH brute force, SQL injection, malware indicators, credential stuffing)
3. Agent wakes up every 10 seconds, reads new content from each file (byte offset tracking), and POSTs to the backend
4. On next cycle, only NEW lines since last read are sent (no duplicates)

### Stop Everything

Press `Ctrl+C` in each terminal. All three components shut down gracefully.

---

## 2. Testing Retry & Buffer

### Simulate backend downtime

1. Start simulator + agent as above
2. Stop the mock backend (`Ctrl+C` in Terminal 1)
3. Watch Terminal 3 — agent logs retry attempts with backoff (2s, 4s, 8s)
4. After retries fail, batches are saved to `agent/buffer/`
5. Restart the mock backend
6. On next cycle, agent drains the buffer first, then reads new content

### Verify buffer contents

```bash
ls agent/buffer/
cat agent/buffer/*.json | python -m json.tool
```

Each file is a complete batch payload ready to be re-sent.

---

## 3. Running Tests

```bash
cd agent/
pip install pytest responses
pytest tests/ -v
```

Expected: 65 passed.

---

## 4. Production Deployment (VM1 Linux)

### Install

```bash
ssh ubuntu@vm1
sudo mkdir -p /opt/sentinel-agent
sudo cp agent.py simulator.py config.json requirements.txt /opt/sentinel-agent/
cd /opt/sentinel-agent
pip install -r requirements.txt
```

### Configure

Edit `/opt/sentinel-agent/config.json`:
```json
{
  "backend_url": "http://10.0.0.4:8000",
  "api_key": "<real API key from M2>",
  "source_vm": "vm1-linux",
  "poll_interval_seconds": 60,
  "log_sources": [
    {"path": "/var/log/sentinel-sim/intrusion.log", "log_type": "intrusion"},
    {"path": "/var/log/sentinel-sim/web.log", "log_type": "web"},
    {"path": "/var/log/sentinel-sim/malware.log", "log_type": "malware"},
    {"path": "/var/log/sentinel-sim/http.log", "log_type": "http"}
  ]
}
```

### Install systemd services

```bash
sudo cp sentinel-agent.service /etc/systemd/system/
sudo cp sentinel-simulator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sentinel-simulator
sudo systemctl enable --now sentinel-agent
```

### Verify

```bash
sudo systemctl status sentinel-agent
sudo systemctl status sentinel-simulator
journalctl -u sentinel-agent -f
```

---

## 5. Production Deployment (VM2 Windows)

See `NSSM-README.md` for Windows Service setup.

---

## 6. Tamper Testing (Run on VM3)

Once M2's backend has stored batches in PostgreSQL:

```bash
# Tamper a specific batch
python tamper.py --db-url postgresql://user:pass@10.0.0.4:5432/sentinel --batch-id 5

# Tamper a random batch for a VM
python tamper.py --db-url postgresql://user:pass@10.0.0.4:5432/sentinel --source-vm vm1-linux
```

Then check the dashboard — the tampered batch should show a red TAMPERED badge within one verification cycle.
