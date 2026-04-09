import os
import random
import time
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HOSTNAME = "vm1-linux"
NORMAL_IPS = ["10.0.0.1", "10.0.0.5", "10.0.0.10", "172.16.0.2", "192.168.1.1"]
ATTACK_IPS = ["192.168.1.100", "203.0.113.50", "198.51.100.77"]
USERS = ["admin", "deploy", "www-data", "ubuntu"]
PATHS = ["/index.html", "/api/users", "/dashboard", "/static/style.css", "/api/health"]


def _ts_syslog():
    now = datetime.now()
    return now.strftime("%b %d %H:%M:%S")  # e.g. "Apr  7 14:23:01"


def _ts_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Normal line generators ---

def generate_intrusion_lines(count: int) -> list:
    lines = []
    for _ in range(count):
        ip = random.choice(NORMAL_IPS)
        user = random.choice(USERS)
        proc = random.choice(["sshd", "sudo", "login"])
        pid = random.randint(1000, 9999)
        templates = [
            f"{_ts_syslog()} {HOSTNAME} {proc}[{pid}]: Accepted password for {user} from {ip} port 22 ssh2",
            f"{_ts_syslog()} {HOSTNAME} {proc}[{pid}]: session opened for user {user} by (uid=0)",
            f"{_ts_syslog()} {HOSTNAME} {proc}[{pid}]: pam_unix(sshd:session): session closed for user {user}",
            f"{_ts_syslog()} {HOSTNAME} CRON[{pid}]: pam_unix(cron:session): session opened for user root",
        ]
        lines.append(random.choice(templates))
    return lines


def generate_web_lines(count: int) -> list:
    lines = []
    for _ in range(count):
        ip = random.choice(NORMAL_IPS)
        path = random.choice(PATHS)
        code = random.choice([200, 200, 200, 301, 304])
        size = random.randint(200, 15000)
        method = random.choice(["GET", "GET", "GET", "POST"])
        lines.append(f'{ip} - - [{datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000")}] "{method} {path} HTTP/1.1" {code} {size}')
    return lines


def generate_malware_lines(count: int) -> list:
    lines = []
    for _ in range(count):
        pid = random.randint(1000, 9999)
        templates = [
            f"{_ts_syslog()} {HOSTNAME} kernel: [UFW ALLOW] IN=eth0 SRC={random.choice(NORMAL_IPS)} DST=10.0.0.2 PROTO=TCP DPT={random.choice([80, 443, 22])}",
            f"{_ts_syslog()} {HOSTNAME} clamd[{pid}]: /home/{random.choice(USERS)}/document.pdf: OK",
            f"{_ts_syslog()} {HOSTNAME} systemd[1]: Started Daily apt download activities.",
        ]
        lines.append(random.choice(templates))
    return lines


def generate_http_lines(count: int) -> list:
    lines = []
    for _ in range(count):
        ip = random.choice(NORMAL_IPS)
        path = random.choice(PATHS)
        method = random.choice(["GET", "POST", "PUT", "DELETE"])
        code = random.choice([200, 200, 200, 201, 204])
        ms = random.randint(1, 50)
        lines.append(f"{_ts_iso()} {method} {path} {code} {ms}ms {ip}")
    return lines


# --- Attack generators ---

def generate_attack_intrusion() -> list:
    ip = random.choice(ATTACK_IPS)
    pid = random.randint(1000, 9999)
    lines = []
    for _ in range(random.randint(5, 12)):
        user = random.choice(["root", "admin", "test", "guest"])
        lines.append(f"{_ts_syslog()} {HOSTNAME} sshd[{pid}]: Failed password for {user} from {ip} port 22 ssh2")
    lines.append(f"{_ts_syslog()} {HOSTNAME} sshd[{pid}]: maximum authentication attempts exceeded for {user} from {ip}")
    return lines


def generate_attack_web() -> list:
    ip = random.choice(ATTACK_IPS)
    attacks = [
        f"GET /search?q=1'+OR+'1'='1 HTTP/1.1",
        f"GET /search?q='+UNION+SELECT+username,password+FROM+users-- HTTP/1.1",
        f"GET /admin/../../../etc/passwd HTTP/1.1",
        f"POST /login HTTP/1.1",
        f"GET /search?q=';DROP+TABLE+users;-- HTTP/1.1",
    ]
    ts = datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000")
    return [f'{ip} - - [{ts}] "{a}" {random.choice([400, 403, 500])} 0' for a in random.sample(attacks, k=random.randint(3, 5))]


def generate_attack_malware() -> list:
    ip = random.choice(ATTACK_IPS)
    pid = random.randint(1000, 9999)
    lines = [
        f"{_ts_syslog()} {HOSTNAME} kernel: [UFW BLOCK] IN=eth0 SRC={ip} DST=10.0.0.2 PROTO=TCP DPT=4444",
        f"{_ts_syslog()} {HOSTNAME} kernel: [UFW BLOCK] IN=eth0 SRC={ip} DST=10.0.0.2 PROTO=TCP DPT=4445",
        f"{_ts_syslog()} {HOSTNAME} clamd[{pid}]: /tmp/.hidden/payload.exe: Win.Trojan.Agent FOUND",
        f"{_ts_syslog()} {HOSTNAME} kernel: [UFW BLOCK] IN=eth0 SRC={ip} DST=10.0.0.2 PROTO=TCP DPT=31337",
    ]
    return random.sample(lines, k=random.randint(3, 4))


def generate_attack_http() -> list:
    ip = random.choice(ATTACK_IPS)
    lines = []
    for _ in range(random.randint(5, 10)):
        ms = random.randint(1, 5)
        lines.append(f"{_ts_iso()} POST /api/login 401 {ms}ms {ip}")
    lines.append(f"{_ts_iso()} POST /api/login 200 {random.randint(10, 30)}ms {ip}")
    return lines


# --- File writing ---

def append_to_file(filepath: str, lines: list):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "a") as f:
        for line in lines:
            f.write(line + "\n")


# --- Main loop ---

GENERATORS = {
    "intrusion": (generate_intrusion_lines, generate_attack_intrusion),
    "web": (generate_web_lines, generate_attack_web),
    "malware": (generate_malware_lines, generate_attack_malware),
    "http": (generate_http_lines, generate_attack_http),
}


def run_simulator(output_dir: str, interval: float = 5.0, hostname: str = "vm1-linux"):
    import signal
    global HOSTNAME
    HOSTNAME = hostname

    running = True

    def shutdown(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    os.makedirs(output_dir, exist_ok=True)
    logging.info("Simulator started, writing to %s", output_dir)

    while running:
        for log_type, (normal_gen, attack_gen) in GENERATORS.items():
            count = random.randint(5, 15)
            lines = normal_gen(count)
            if random.random() < 0.3:
                lines.extend(attack_gen())
                logging.info("Injected attack into %s", log_type)
            filepath = os.path.join(output_dir, f"{log_type}.log")
            append_to_file(filepath, lines)

        delay = interval + random.uniform(-1, 1)
        if running:
            time.sleep(max(1, delay))

    logging.info("Simulator stopped.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sentinel-Chain Log Simulator")
    parser.add_argument("--output-dir", default="./sim_logs", help="Directory to write log files")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between writes")
    parser.add_argument("--hostname", default="vm1-linux", help="Hostname to use in log lines")
    args = parser.parse_args()
    run_simulator(args.output_dir, args.interval, args.hostname)
