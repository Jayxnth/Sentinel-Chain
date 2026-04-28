from __future__ import annotations

from datetime import datetime, timedelta, timezone


NOW = datetime.now(timezone.utc)

SOURCES = [
    {
        "source_vm": "vm1-linux",
        "label": "VM1 Linux Agent",
        "platform": "Linux",
        "status": "VERIFIED",
        "last_seen": (NOW - timedelta(minutes=4)).isoformat(),
        "batch_count": 42,
        "log_counts": {"intrusion": 15, "web": 12, "malware": 7, "http": 8},
    },
    {
        "source_vm": "vm2-windows",
        "label": "VM2 Windows Agent",
        "platform": "Windows",
        "status": "TAMPERED",
        "last_seen": (NOW - timedelta(minutes=11)).isoformat(),
        "batch_count": 36,
        "log_counts": {"intrusion": 8, "web": 9, "malware": 6, "http": 13},
    },
]

BATCHES = [
    {
        "id": 109,
        "source_vm": "vm2-windows",
        "log_type": "malware",
        "filename": "defender-events.log",
        "integrity_status": "TAMPERED",
        "ts": (NOW - timedelta(minutes=9)).isoformat(),
    },
    {
        "id": 108,
        "source_vm": "vm1-linux",
        "log_type": "intrusion",
        "filename": "auth.log",
        "integrity_status": "VERIFIED",
        "ts": (NOW - timedelta(minutes=17)).isoformat(),
    },
    {
        "id": 107,
        "source_vm": "vm1-linux",
        "log_type": "web",
        "filename": "apache-access.log",
        "integrity_status": "VERIFIED",
        "ts": (NOW - timedelta(minutes=26)).isoformat(),
    },
    {
        "id": 106,
        "source_vm": "vm2-windows",
        "log_type": "http",
        "filename": "iis.log",
        "integrity_status": "VERIFIED",
        "ts": (NOW - timedelta(minutes=39)).isoformat(),
    },
]

REPORTS = [
    {
        "id": 301,
        "batch_id": 109,
        "source_vm": "vm2-windows",
        "log_type": "malware",
        "severity": "CRITICAL",
        "summary": "Tamper evidence and malware indicators were detected in the Windows log stream.",
        "findings": (
            "Hash chain validation failed at batch 109. The batch also contains Defender-style "
            "detections for a suspicious payload in AppData and repeated outbound attempts to TCP/4444."
        ),
        "recommendations": (
            "Isolate VM2 from the network. Preserve disk and memory evidence. Rotate credentials "
            "used on the host and block the remote endpoint at the firewall."
        ),
        "integrity_status": "VERIFIED",
        "ts": (NOW - timedelta(minutes=8)).isoformat(),
    },
    {
        "id": 300,
        "batch_id": 108,
        "source_vm": "vm1-linux",
        "log_type": "intrusion",
        "severity": "HIGH",
        "summary": "SSH brute-force behavior targeted privileged accounts on the Linux agent.",
        "findings": (
            "The same external IP generated more than 30 failed password attempts against root and "
            "admin in a short interval, followed by one sudo attempt by an unapproved user."
        ),
        "recommendations": "Block the source IP, enable fail2ban, and audit privileged SSH access.",
        "integrity_status": "VERIFIED",
        "ts": (NOW - timedelta(minutes=16)).isoformat(),
    },
    {
        "id": 299,
        "batch_id": 107,
        "source_vm": "vm1-linux",
        "log_type": "web",
        "severity": "MEDIUM",
        "summary": "Web logs show probing for SQL injection and path traversal.",
        "findings": "Requests included UNION SELECT payloads and ../../etc/passwd probes against public routes.",
        "recommendations": "Review WAF rules, verify input validation, and inspect access logs for follow-up requests.",
        "integrity_status": "VERIFIED",
        "ts": (NOW - timedelta(minutes=25)).isoformat(),
    },
    {
        "id": 298,
        "batch_id": 106,
        "source_vm": "vm2-windows",
        "log_type": "http",
        "severity": "LOW",
        "summary": "Routine HTTP traffic with a small number of failed login attempts.",
        "findings": "No clear attack chain was found. Failed login activity stayed below alert threshold.",
        "recommendations": "Continue monitoring and keep authentication rate limits enabled.",
        "integrity_status": "VERIFIED",
        "ts": (NOW - timedelta(minutes=38)).isoformat(),
    },
]

INTEGRITY = {
    "vm1-linux": {
        "status": "VERIFIED",
        "tampered_batch_id": None,
        "batch_count": 42,
        "last_verified_ts": (NOW - timedelta(minutes=4)).isoformat(),
    },
    "vm2-windows": {
        "status": "TAMPERED",
        "tampered_batch_id": 109,
        "batch_count": 36,
        "last_verified_ts": (NOW - timedelta(minutes=9)).isoformat(),
    },
}


def _filtered_reports(source_vm: str | None = None, log_type: str | None = None) -> list[dict]:
    results = list(REPORTS)
    if source_vm and source_vm != "All":
        results = [report for report in results if report.get("source_vm") == source_vm]
    if log_type and log_type != "All":
        results = [report for report in results if report.get("log_type") == log_type]
    return results


def _citation(report: dict, line: str) -> dict:
    return {
        "batch_id": report.get("batch_id"),
        "source_vm": report.get("source_vm"),
        "log_line": line,
        "ts": report.get("ts"),
    }


def mock_query(question: str, source_vm: str | None = None, log_type: str | None = None) -> dict:
    query = question.lower().strip()
    scoped_reports = _filtered_reports(source_vm, log_type)
    scope = ", ".join(value for value in [source_vm, log_type] if value and value != "All")
    scoped = f" for {scope}" if scope else ""

    vague_prompts = {"what", "what?", "what is this", "what is this?", "what do you mean", "what do you mean?"}
    known_terms = {
        "urgent",
        "threat",
        "report",
        "reports",
        "remediation",
        "malware",
        "callback",
        "outbound",
        "ssh",
        "brute",
        "login",
        "sql",
        "injection",
        "web",
        "tamper",
        "integrity",
    }
    if query in vague_prompts or (len(query.split()) <= 3 and not any(term in query for term in known_terms)):
        return {
            "answer": (
                "I need a more specific question to answer from the mock evidence. Try asking about "
                "the most urgent threat, malware callbacks, SSH brute force, web attacks, integrity, "
                "or which reports need remediation."
            ),
            "citations": [],
        }

    if not scoped_reports:
        return {
            "answer": (
                f"I do not have matching mock evidence{scoped}. Change the Source VM or Log type filter, "
                "or switch to Live mode after the backend API key is accepted."
            ),
            "citations": [],
        }

    if "malware" in query or "callback" in query or "outbound" in query or "4444" in query:
        malware_reports = [report for report in scoped_reports if report.get("log_type") == "malware"]
        if not malware_reports:
            return {
                "answer": (
                    f"No malware or outbound callback evidence appears in the current mock filter{scoped}. "
                    "The malware evidence is in vm2-windows with log type malware."
                ),
                "citations": [],
            }
        report = malware_reports[0]
        return {
            "answer": (
                "Yes. The mock evidence shows Defender-style malware detection plus repeated outbound "
                "traffic to TCP/4444. This should be treated as the most urgent containment item. [Source 1]"
            ),
            "citations": [
                _citation(report, "Defender detected payload.exe and outbound TCP/4444 after chain mismatch.")
            ],
        }

    if "ssh" in query or "brute" in query or "login" in query:
        intrusion_reports = [report for report in scoped_reports if report.get("log_type") == "intrusion"]
        if not intrusion_reports:
            return {
                "answer": (
                    f"No SSH brute-force evidence appears in the current mock filter{scoped}. "
                    "Try vm1-linux with log type intrusion."
                ),
                "citations": [],
            }
        report = intrusion_reports[0]
        return {
            "answer": (
                "The current filter shows SSH brute-force behavior against privileged accounts. "
                "Block the repeated source IP, enable fail2ban, and audit privileged SSH access. [Source 1]"
            ),
            "citations": [
                _citation(report, "Failed password attempts targeted root/admin repeatedly from the same remote address.")
            ],
        }

    if "sql" in query or "injection" in query or "path traversal" in query or "web" in query:
        web_reports = [report for report in scoped_reports if report.get("log_type") == "web"]
        if not web_reports:
            return {
                "answer": (
                    f"No web attack evidence appears in the current mock filter{scoped}. "
                    "Try vm1-linux with log type web."
                ),
                "citations": [],
            }
        report = web_reports[0]
        return {
            "answer": (
                "The mock web report shows SQL injection probes and path traversal attempts. "
                "Review WAF rules and verify input validation on the affected routes. [Source 1]"
            ),
            "citations": [
                _citation(report, "Requests included UNION SELECT payloads and ../../etc/passwd probes.")
            ],
        }

    urgent = sorted(
        scoped_reports,
        key=lambda report: {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "CLEAN": 0}.get(report.get("severity"), 0),
        reverse=True,
    )[0]
    return {
        "answer": (
            f"The most urgent matching mock report{scoped} is {urgent.get('severity')} on "
            f"{urgent.get('source_vm')} / {urgent.get('log_type')}: {urgent.get('summary')} "
            f"Recommended first action: {urgent.get('recommendations')} [Source 1]"
        ),
        "citations": [_citation(urgent, urgent.get("findings", "Matching mock report evidence."))],
    }
