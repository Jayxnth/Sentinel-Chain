# Sentinel-Chain API Contract

This document defines all backend endpoints for the Sentinel-Chain project. It is intended for frontend integration (M4).

**Base URL:** `http://<host>:<port>`  
**Authentication:** All endpoints require the `X-API-Key` header unless otherwise noted.

---

## Table of Contents

- [POST /ingest](#post-ingest)
- [GET /reports](#get-reports)
- [POST /query](#post-query)
- [GET /integrity](#get-integrity)
- [POST /upload](#post-upload)
- [GET /health](#get-health)

---

## POST /ingest

Ingest a log entry from a VM, run AI analysis, and store the result on-chain.

### Headers

| Header      | Required | Description              |
|-------------|----------|--------------------------|
| X-API-Key   | Yes      | API authentication key   |
| Content-Type| Yes      | `application/json`       |

### Request Body

```json
{
  "source_vm": "string",
  "log_type": "string",
  "content": "string",
  "filename": "string",
  "ts": "string (ISO 8601 datetime)"
}
```

| Field      | Type   | Required | Description                                      |
|------------|--------|----------|--------------------------------------------------|
| source_vm  | string | Yes      | Identifier of the source VM (e.g. `"vm-prod-01"`) |
| log_type   | string | Yes      | Category of log (`"malware"`, `"intrusion"`, `"web"`, `"http"`) |
| content    | string | Yes      | Raw log content to be analyzed                   |
| filename   | string | Yes      | Original filename of the log                     |
| ts         | string | Yes      | Timestamp of the log entry in ISO 8601 format (e.g. `"2026-04-04T12:00:00Z"`) |

### Example Request

```json
{
  "source_vm": "vm-prod-01",
  "log_type": "intrusion",
  "content": "Failed password for root from 192.168.1.100 port 22 ssh2",
  "filename": "auth.log",
  "ts": "2026-04-04T12:00:00Z"
}
```

### Response Body

```json
{
  "batch_id": 42,
  "integrity_status": "VERIFIED",
  "report_id": 17
}
```

| Field            | Type    | Description                                                |
|------------------|---------|------------------------------------------------------------|
| batch_id         | integer | Unique ID of the ingested log batch stored on-chain        |
| integrity_status | string  | `"VERIFIED"` if the chain is intact, `"TAMPERED"` if not  |
| report_id        | integer\|null | ID of the AI-generated analysis report, or `null` if `integrity_status` is `"TAMPERED"` or AI analysis failed |

### Status Codes

| Code | Meaning                                              |
|------|------------------------------------------------------|
| 200  | Log ingested and analyzed successfully               |
| 400  | Malformed request body or missing required fields    |
| 401  | Missing or invalid `X-API-Key`                       |
| 500  | Internal server error during ingestion or AI analysis|

---

## GET /reports

Retrieve a paginated list of AI-generated analysis reports, with optional filters.

### Headers

| Header    | Required | Description            |
|-----------|----------|------------------------|
| X-API-Key | Yes      | API authentication key |

### Query Parameters

| Parameter | Type    | Required | Default | Description                                |
|-----------|---------|----------|---------|--------------------------------------------|
| source_vm | string  | No       | —       | Filter by source VM identifier             |
| log_type  | string  | No       | —       | Filter by log type                         |
| severity  | string  | No       | —       | Filter by severity (`"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"CLEAN"`) |
| page      | integer | No       | `1`     | Page number for pagination                 |
| page_size | integer | No       | `20`    | Number of results per page                 |

### Example Request

```
GET /reports?source_vm=vm-prod-01&severity=HIGH&page=1&page_size=10
```

### Response Body

```json
[
  {
    "id": 17,
    "batch_id": 42,
    "source_vm": "vm-prod-01",
    "log_type": "intrusion",
    "severity": "HIGH",
    "summary": "Multiple failed SSH login attempts detected from a single IP.",
    "findings": "192.168.1.100 made 47 failed login attempts targeting root over 3 minutes.",
    "recommendations": "Block IP 192.168.1.100 via firewall. Enable fail2ban. Review SSH access policy.",
    "ts": "2026-04-04T12:00:00Z"
  }
]
```

| Field           | Type    | Description                                             |
|-----------------|---------|---------------------------------------------------------|
| id              | integer | Unique report ID                                        |
| batch_id        | integer | ID of the associated on-chain log batch                 |
| source_vm       | string  | Source VM identifier                                    |
| log_type        | string  | Log category                                            |
| severity        | string  | Assessed severity: `"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, or `"CLEAN"` |
| summary         | string  | Short AI-generated summary of the log analysis          |
| findings        | string  | Detailed findings from the AI analysis                  |
| recommendations | string  | AI-generated remediation recommendations                |
| ts              | string  | ISO 8601 timestamp of the original log entry            |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | Reports returned successfully (may be empty array)|
| 401  | Missing or invalid `X-API-Key`                    |
| 500  | Internal server error                             |

---

## POST /query

Ask a natural language question about ingested logs and receive an AI-generated answer.

### Headers

| Header      | Required | Description            |
|-------------|----------|------------------------|
| X-API-Key   | Yes      | API authentication key |
| Content-Type| Yes      | `application/json`     |

### Request Body

```json
{
  "question": "string",
  "source_vm": "string (optional)",
  "log_type": "string (optional)"
}
```

| Field     | Type   | Required | Description                                         |
|-----------|--------|----------|-----------------------------------------------------|
| question  | string | Yes      | Natural language question about the log data        |
| source_vm | string | No       | Scope the query to a specific source VM             |
| log_type  | string | No       | Scope the query to a specific log type              |

### Example Request

```json
{
  "question": "Were there any brute force attempts in the last 24 hours?",
  "source_vm": "vm-prod-01",
  "log_type": "intrusion"
}
```

### Response Body

```json
{
  "answer": "Yes. vm-prod-01 recorded 47 failed SSH login attempts from 192.168.1.100 between 11:58 and 12:01 UTC on 2026-04-04, consistent with a brute force attack."
}
```

| Field  | Type   | Description                          |
|--------|--------|--------------------------------------|
| answer | string | AI-generated answer to the question  |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | Answer generated successfully                     |
| 400  | Missing or invalid `question` field               |
| 401  | Missing or invalid `X-API-Key`                    |
| 500  | Internal server error during AI query             |
| 503  | No logs have been ingested yet (ChromaDB empty)   |

---

## GET /integrity

Check the blockchain integrity status for all VMs, or for a specific VM.

### Headers

| Header    | Required | Description            |
|-----------|----------|------------------------|
| X-API-Key | Yes      | API authentication key |

### Query Parameters

| Parameter | Type   | Required | Description                                      |
|-----------|--------|----------|--------------------------------------------------|
| source_vm | string | No       | If provided, returns status for that VM only     |

### Example Request

```
GET /integrity?source_vm=vm-prod-01
```

### Response Body

```json
{
  "vm-prod-01": {
    "status": "VERIFIED",
    "tampered_batch_id": null
  },
  "vm-staging-02": {
    "status": "TAMPERED",
    "tampered_batch_id": 38
  }
}
```

The response is a dictionary keyed by VM identifier.

| Field             | Type         | Description                                                              |
|-------------------|--------------|--------------------------------------------------------------------------|
| status            | string       | `"VERIFIED"` if the chain for this VM is intact, `"TAMPERED"` if not    |
| tampered_batch_id | integer\|null| The batch ID where tampering was detected, or `null` if status is `"VERIFIED"` |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | Integrity data returned successfully              |
| 401  | Missing or invalid `X-API-Key`                    |
| 500  | Internal server error during integrity check      |

---

## POST /upload

Upload a log file directly. The backend will parse and ingest it automatically.

### Headers

| Header       | Required | Description                                  |
|--------------|----------|----------------------------------------------|
| X-API-Key    | Yes      | API authentication key                       |
| Content-Type | Yes      | `multipart/form-data`                        |

### Request Body

Multipart form upload. The file should be provided under the `file` field.

| Field | Type | Required | Description              |
|-------|------|----------|--------------------------|
| file  | file | Yes      | The log file to upload   |

### Example Request (curl)

```bash
curl -X POST http://<host>:<port>/upload \
  -H "X-API-Key: <your-api-key>" \
  -F "file=@/path/to/auth.log"
```

### Response Body

```json
{
  "filename": "auth.log",
  "status": "ingested"
}
```

| Field    | Type   | Description                              |
|----------|--------|------------------------------------------|
| filename | string | Name of the uploaded file                |
| status   | string | Always `"ingested"` on success           |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | File uploaded and ingested successfully           |
| 400  | No file provided or unsupported file format       |
| 401  | Missing or invalid `X-API-Key`                    |
| 500  | Internal server error during file processing      |

---

## GET /health

Check that the API server is running. No authentication required.

### Headers

None required.

### Response Body

```json
{
  "status": "ok"
}
```

| Field  | Type   | Description               |
|--------|--------|---------------------------|
| status | string | Always `"ok"` when alive  |

### Status Codes

| Code | Meaning                        |
|------|--------------------------------|
| 200  | Service is healthy and running |
| 500  | Service is unhealthy           |

---

## Error Response Format

All error responses follow a consistent shape:

```json
{
  "error": "Human-readable description of what went wrong."
}
```

| Field | Type   | Description             |
|-------|--------|-------------------------|
| error | string | Description of the error|

---

*Last updated: 2026-04-04*
