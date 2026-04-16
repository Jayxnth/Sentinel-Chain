import json
import os
import time
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

VALID_LOG_TYPES = {"malware", "intrusion", "web", "http"}
REQUIRED_FIELDS = ["backend_url", "api_key", "source_vm", "log_sources"]


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        cfg = json.load(f)

    for field in REQUIRED_FIELDS:
        if field not in cfg:
            raise KeyError(f"Missing required config field: {field}")

    for i, src in enumerate(cfg["log_sources"]):
        if "path" not in src:
            raise KeyError(f"log_sources[{i}] missing 'path'")
        if "log_type" not in src:
            raise KeyError(f"log_sources[{i}] missing 'log_type'")
        if src["log_type"] not in VALID_LOG_TYPES:
            raise ValueError(f"log_sources[{i}] invalid log_type: {src['log_type']}")

    return cfg


def load_state(path: str) -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict, path: str):
    with open(path, "w") as f:
        json.dump(state, f)


def read_new_content(filepath: str, state: dict) -> tuple:
    if not os.path.exists(filepath):
        return None, None

    file_size = os.path.getsize(filepath)
    offset = state.get(filepath, {}).get("offset", 0)

    if file_size < offset:
        offset = 0

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(offset)
        content = f.read()

    return content, offset + len(content.encode("utf-8"))


MAX_RETRIES = 3
BACKOFF_BASE = 2


def send_batch(payload: dict, backend_url: str, api_key: str) -> dict:
    url = f"{backend_url}/ingest"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    for attempt in range(1 + MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                logging.info("Sent batch (%s, %d bytes) → batch_id=%s", payload.get("log_type", "?"), len(payload.get("content", "")), data.get("batch_id"))
                return {"success": True, "batch_id": data.get("batch_id"), "integrity_status": data.get("integrity_status")}

            if resp.status_code in (400, 401):
                logging.error("Client error %d from backend: %s", resp.status_code, resp.text)
                return {"success": False, "status_code": resp.status_code}

            # Server error — retry
            if attempt < MAX_RETRIES:
                delay = BACKOFF_BASE ** (attempt + 1)
                logging.warning("Server error %d, retrying in %ds...", resp.status_code, delay)
                time.sleep(delay)

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < MAX_RETRIES:
                delay = BACKOFF_BASE ** (attempt + 1)
                logging.warning("Network error: %s, retrying in %ds...", e, delay)
                time.sleep(delay)

    logging.error("All retries exhausted for batch")
    return {"success": False}


def save_to_buffer(payload: dict, buffer_dir: str):
    os.makedirs(buffer_dir, exist_ok=True)
    filename = f"{time.time():.6f}_{payload.get('filename', 'unknown')}.json"
    path = os.path.join(buffer_dir, filename)
    with open(path, "w") as f:
        json.dump(payload, f)


def drain_buffer(buffer_dir: str, backend_url: str, api_key: str):
    if not os.path.exists(buffer_dir):
        return
    files = sorted(os.listdir(buffer_dir))
    for fname in files:
        path = os.path.join(buffer_dir, fname)
        try:
            with open(path, "r") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, IOError):
            logging.warning("Corrupted buffer file %s, removing", fname)
            os.remove(path)
            continue
        result = send_batch(payload, backend_url, api_key)
        if result["success"]:
            os.remove(path)
        else:
            break


def run_cycle(cfg: dict, state_path: str, buffer_dir: str) -> dict:
    state = load_state(state_path)
    drain_buffer(buffer_dir, cfg["backend_url"], cfg["api_key"])

    for src in cfg["log_sources"]:
        content, new_offset = read_new_content(src["path"], state)
        if not content:
            continue

        payload = {
            "source_vm": cfg["source_vm"],
            "log_type": src["log_type"],
            "content": content,
            "filename": os.path.basename(src["path"]),
            "ts": _now_iso(),
        }

        result = send_batch(payload, cfg["backend_url"], cfg["api_key"])
        if result["success"]:
            state[src["path"]] = {"offset": new_offset}
        else:
            save_to_buffer(payload, buffer_dir)

    save_state(state, state_path)
    return state


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    import signal
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    cfg = load_config(config_path)
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".agent_state.json")
    buffer_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "buffer")

    running = True

    def shutdown(signum, frame):
        nonlocal running
        logging.info("Shutting down...")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logging.info("Sentinel Agent started (source_vm=%s, interval=%ds)", cfg["source_vm"], cfg.get("poll_interval_seconds", 60))

    while running:
        try:
            run_cycle(cfg, state_path, buffer_dir)
        except Exception as e:
            logging.error("Cycle error: %s", e)
        if running:
            time.sleep(cfg.get("poll_interval_seconds", 60))

    logging.info("Agent stopped.")


if __name__ == "__main__":
    main()
