# Sentinel-Chain API Contract

This document defines all backend endpoints for the Sentinel-Chain project. It is intended for frontend integration (M4).

**Base URL:** `http://<host>:<port>`  
**Authentication:** All endpoints require the `X-API-Key` header unless otherwise noted.

---

## Table of Contents

- [POST /ingest](#post-ingest)
- [GET /batches](#get-batches)
- [GET /reports](#get-reports)
- [POST /query](#post-query)
- [GET /integrity](#get-integrity)
- [POST /upload](#post-upload)
- [GET /health](#get-health)

---

## POST /ingest

Ingest a log batch from a VM, verify chain integrity, and store the result on-chain. AI analysis runs synchronously as part of the ingest request. The response includes the generated `report_id` on success. Typical latency is 5–30 seconds depending on batch size and Gemini API load. The client should set a request timeout of at least 90 seconds.

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
| log_type   | string | Yes      | Category of log. Accepted values: `"malware"`, `"intrusion"`, `"web"`, `"http"`. The backend returns `400` if an unrecognized value is provided. |
| content    | string | Yes      | Raw log content to be analyzed                   |
| filename   | string | Yes      | Original filename of the log                     |
| ts         | string | Yes      | Timestamp of the log batch collection time in ISO 8601 format (e.g. `"2026-04-04T12:00:00Z"`). This is the agent-reported collection time. The backend trusts this value for timeline ordering. |

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

| Field            | Type             | Description                                                |
|------------------|------------------|------------------------------------------------------------|
| batch_id         | integer          | Unique ID of the ingested log batch stored on-chain        |
| integrity_status | string           | `"VERIFIED"` if the chain is intact, `"TAMPERED"` if not, `"ERROR"` if the integrity check itself failed (e.g. database read error). On `"ERROR"`, the batch is still stored but not analyzed. |
| report_id        | integer \| null  | ID of the generated threat report. `null` if AI analysis failed or timed out. The field is always present in responses where `integrity_status` is `VERIFIED`. |
| warning          | string, optional | Present only if AI analysis failed or timed out. Human-readable explanation. |

### Status Codes

| Code | Meaning                                              |
|------|------------------------------------------------------|
| 200  | Log ingested successfully. Check `integrity_status` in the response body for the outcome of integrity verification. AI analysis runs asynchronously - poll `GET /reports?batch_id=<batch_id>` to retrieve results. |
| 400  | Malformed request body or missing required fields    |
| 401  | Missing or invalid `X-API-Key`                       |
| 500  | Internal server error during ingestion (batch was NOT stored) |
| 503  | Database unavailable                                 |

---

## GET /batches

Retrieve a paginated, chronological list of all ingestion events. Includes both `VERIFIED` and `TAMPERED` batches.

### Headers

| Header    | Required | Description            |
|-----------|----------|------------------------|
| X-API-Key | Yes      | API authentication key |

### Query Parameters

| Parameter | Type    | Required | Default | Description                                |
|-----------|---------|----------|---------|--------------------------------------------|
| source_vm | string  | No       | -       | Filter by source VM identifier             |
| page      | integer | No       | `1`     | Page number for pagination                 |
| page_size | integer | No       | `20`    | Number of results per page (max `100`)     |

### Example Request

```
GET /batches?source_vm=vm-prod-01&page=1&page_size=20
```

### Response Body

```json
{
  "results": [
    {
      "id": 42,
      "source_vm": "vm-prod-01",
      "log_type": "intrusion",
      "filename": "auth.log",
      "integrity_status": "VERIFIED",
      "ts": "2026-04-04T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

| Field     | Type    | Description                                          |
|-----------|---------|------------------------------------------------------|
| results   | array   | Array of batch objects for the current page           |
| total     | integer | Total number of batches matching the applied filters  |
| page      | integer | Current page number                                   |
| page_size | integer | Number of results per page                            |

**Batch object fields:**

| Field            | Type    | Description                                      |
|------------------|---------|--------------------------------------------------|
| id               | integer | Unique batch ID                                  |
| source_vm        | string  | Source VM identifier                             |
| log_type         | string  | Log category                                     |
| filename         | string  | Original filename of the log                     |
| integrity_status | string  | `"VERIFIED"`, `"TAMPERED"`, or `"ERROR"`         |
| ts               | string  | ISO 8601 timestamp of the log batch collection time |

### Status Codes

| Code | Meaning                                              |
|------|------------------------------------------------------|
| 200  | Batches returned successfully (results array may be empty) |
| 401  | Missing or invalid `X-API-Key`                       |
| 500  | Internal server error                                |

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
| batch_id  | integer | No       | -       | Filter by batch ID. Use this to check whether a report has been generated for a specific ingestion (e.g. `GET /reports?batch_id=42`). |
| source_vm | string  | No       | -       | Filter by source VM identifier             |
| log_type  | string  | No       | -       | Filter by log type                         |
| severity  | string  | No       | -       | Filter by severity (`"CRITICAL"`, `"HIGH"`, `"MEDIUM"`, `"LOW"`, `"CLEAN"`) |
| from_ts   | string  | No       | -       | Return only reports with `ts` at or after this ISO 8601 timestamp |
| to_ts     | string  | No       | -       | Return only reports with `ts` at or before this ISO 8601 timestamp |
| page      | integer | No       | `1`     | Page number for pagination                 |
| page_size | integer | No       | `20`    | Number of results per page (max `100`)     |

### Example Request

```
GET /reports?source_vm=vm-prod-01&severity=HIGH&page=1&page_size=10
```

### Response Body

```json
{
  "results": [
    {
      "id": 17,
      "batch_id": 42,
      "source_vm": "vm-prod-01",
      "log_type": "intrusion",
      "severity": "HIGH",
      "summary": "Multiple failed SSH login attempts detected from a single IP.",
      "findings": "192.168.1.100 made 47 failed login attempts targeting root over 3 minutes.",
      "recommendations": "Block IP 192.168.1.100 via firewall. Enable fail2ban. Review SSH access policy.",
      "integrity_status": "VERIFIED",
      "ts": "2026-04-04T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

| Field           | Type    | Description                                             |
|-----------------|---------|---------------------------------------------------------|
| results         | array   | Array of report objects for the current page            |
| total           | integer | Total number of reports matching the applied filters    |
| page            | integer | Current page number                                    |
| page_size       | integer | Number of results per page                              |

**Report object fields:**

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
| integrity_status| string  | Always `"VERIFIED"`. Reports are only generated for batches that pass integrity verification; `TAMPERED` batches skip AI analysis and produce no report. |
| ts              | string  | ISO 8601 timestamp of the original log entry            |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | Reports returned successfully (results array may be empty) |
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
  "log_type": "string (optional)",
  "history": [
    { "role": "user", "content": "string" },
    { "role": "assistant", "content": "string" }
  ]
}
```

| Field     | Type   | Required | Description                                         |
|-----------|--------|----------|-----------------------------------------------------|
| question  | string | Yes      | Natural language question about the log data        |
| source_vm | string | No       | Scope the query to a specific source VM             |
| log_type  | string | No       | Scope the query to a specific log type              |
| history   | array  | No       | Previous conversation turns for multi-turn context. Each item has `role` (`"user"` or `"assistant"`) and `content` (string). If omitted, the query is treated as a standalone question. |

### Example Request (standalone)

```json
{
  "question": "Were there any brute force attempts in the last 24 hours?",
  "source_vm": "vm-prod-01",
  "log_type": "intrusion"
}
```

### Example Request (multi-turn)

```json
{
  "question": "Which IP was responsible?",
  "source_vm": "vm-prod-01",
  "history": [
    { "role": "user", "content": "Were there any brute force attempts in the last 24 hours?" },
    { "role": "assistant", "content": "Yes. vm-prod-01 recorded 47 failed SSH login attempts consistent with a brute force attack." }
  ]
}
```

### Response Body

```json
{
  "answer": "Yes. vm-prod-01 recorded 47 failed SSH login attempts from 192.168.1.100 between 11:58 and 12:01 UTC on 2026-04-04, consistent with a brute force attack.",
  "citations": [
    {
      "batch_id": 42,
      "source_vm": "vm-prod-01",
      "log_line": "Failed password for root from 192.168.1.100 port 22 ssh2",
      "ts": "2026-04-04T11:58:12Z"
    }
  ]
}
```

| Field     | Type   | Description                                                    |
|-----------|--------|----------------------------------------------------------------|
| answer    | string | AI-generated answer to the question                            |
| citations | array  | Log entries the AI referenced when generating the answer. May be empty if the answer is general or no specific logs were retrieved. |

**Citation object fields:**

| Field     | Type    | Description                                      |
|-----------|---------|--------------------------------------------------|
| batch_id  | integer | ID of the log batch containing this entry        |
| source_vm | string  | VM the cited log entry came from                 |
| log_line  | string  | The specific log line referenced                 |
| ts        | string  | ISO 8601 timestamp of the cited log entry        |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | Answer generated successfully. If no logs have been ingested yet, the response body will be `{"answer": "No logs have been ingested yet.", "citations": []}`. |
| 400  | Missing or invalid `question` field               |
| 401  | Missing or invalid `X-API-Key`                    |
| 500  | Internal server error during AI query             |
| 503  | Infrastructure dependency unavailable (e.g. ChromaDB unreachable). Check the `error` field in the response body for the specific reason. |

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
| source_vm | string | No       | If provided, returns status for that VM only. If omitted, returns status for all VMs that have ingested logs. |

### Example Request (filtered)

```
GET /integrity?source_vm=vm-prod-01
```

### Example Response (filtered - single VM)

```json
{
  "vm-prod-01": {
    "status": "VERIFIED",
    "tampered_batch_id": null,
    "batch_count": 12,
    "last_verified_ts": "2026-04-04T12:00:00Z"
  }
}
```

### Example Request (all VMs)

```
GET /integrity
```

### Example Response (all VMs)

```json
{
  "vm-prod-01": {
    "status": "VERIFIED",
    "tampered_batch_id": null,
    "batch_count": 12,
    "last_verified_ts": "2026-04-04T12:00:00Z"
  },
  "vm-staging-02": {
    "status": "TAMPERED",
    "tampered_batch_id": 38,
    "batch_count": 5,
    "last_verified_ts": "2026-04-03T09:15:00Z"
  }
}
```

The response is a dictionary keyed by VM identifier. When `source_vm` is provided, only that VM is included. When omitted, all VMs are included. If `source_vm` is provided but has no ingested logs, the response is an empty object `{}`.

| Field             | Type         | Description                                                                    |
|-------------------|--------------|--------------------------------------------------------------------------------|
| status            | string       | `"VERIFIED"` if the chain for this VM is intact, `"TAMPERED"` if not, `"ERROR"` if the integrity check could not complete. |
| tampered_batch_id | integer\|null| The batch ID where tampering was first detected, or `null` if status is `"VERIFIED"` or `"ERROR"`. |
| batch_count       | integer      | Total number of batches ingested for this VM.                                  |
| last_verified_ts  | string\|null | ISO 8601 timestamp of the most recently verified batch for this VM, or `null` if no batches have been verified. |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | Integrity data returned successfully              |
| 401  | Missing or invalid `X-API-Key`                    |
| 500  | Internal server error during integrity check      |
| 503  | Database unavailable during integrity check       |

---

## POST /upload

Upload a log file directly (max 10 MB). The backend will parse and ingest it automatically.

### Headers

| Header       | Required | Description                                  |
|--------------|----------|----------------------------------------------|
| X-API-Key    | Yes      | API authentication key                       |
| Content-Type | Yes      | `multipart/form-data`                        |

### Request Body

Multipart form upload.

| Field     | Type   | Required | Description                                                    |
|-----------|--------|----------|----------------------------------------------------------------|
| file      | file   | Yes      | The log file to upload                                         |
| source_vm | string | Yes      | Identifier of the source VM this file came from (e.g. `"vm-prod-01"`) |
| log_type  | string | Yes      | Category of log. Same accepted values as `/ingest`: `"malware"`, `"intrusion"`, `"web"`, `"http"`. |

### Example Request (curl)

```bash
curl -X POST http://<host>:<port>/upload \
  -H "X-API-Key: <your-api-key>" \
  -F "file=@/path/to/auth.log" \
  -F "source_vm=vm-prod-01" \
  -F "log_type=intrusion"
```

### Response Body

```json
{
  "filename": "auth.log",
  "status": "ingested",
  "batch_id": 43,
  "integrity_status": "VERIFIED"
}
```

| Field            | Type             | Description                              |
|------------------|------------------|------------------------------------------|
| filename         | string           | Name of the uploaded file                |
| status           | string           | `"ingested"` on success                  |
| batch_id         | integer \| null  | ID of the created log batch. Currently always `null` — uploads do not yet create a LogBatch row. Tracked for a follow-up fix. |
| integrity_status | string           | `"VERIFIED"`, `"TAMPERED"`, or `"ERROR"` |
| report_id        | integer \| null  | ID of the generated threat report. `null` if AI analysis failed or timed out. |

### Status Codes

| Code | Meaning                                           |
|------|---------------------------------------------------|
| 200  | File uploaded and ingested successfully. AI analysis runs asynchronously - poll `GET /reports?batch_id=<batch_id>` to retrieve results. |
| 400  | No file provided or unsupported file format       |
| 401  | Missing or invalid `X-API-Key`                    |
| 413  | File exceeds maximum allowed size of 10 MB        |
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

## Changelog

| Version | Date       | Changes |
|---------|------------|---------|
| v1      | 2026-04-04 | Initial contract |
| v2      | 2026-04-05 | Added pagination metadata to `/reports`. Expanded `/upload` response with `batch_id`, `integrity_status`, `report_id`. Added `source_vm` and `log_type` form fields to `/upload`. Clarified `/integrity` filter behavior with separate examples and empty-VM case. Clarified `"ERROR"` state semantics on `/ingest`. Clarified 503 on `/query` covers both empty DB and unreachable ChromaDB. Added `citations` array to `/query` response. Changed `/ingest` description from "log entry" to "log batch". Defined `log_type` as a controlled set with 400 on invalid values. Added `ts` trust note on `/ingest`. |
| v3      | 2026-04-07 | Removed `report_id` from `/ingest` and `/upload` responses - AI analysis now runs asynchronously. Added `GET /batches` endpoint for chronological batch listing. Added `history` array to `POST /query` for multi-turn conversation support. Added `batch_count` and `last_verified_ts` to `GET /integrity` VM objects. Changed `/ingest` `ts` description to "log batch collection time". Added `from_ts`/`to_ts` date-range filters to `GET /reports`. Added `integrity_status` field to report objects in `GET /reports`. Changed `POST /query` to return 200 with informational message when DB is empty, reserved 503 for infrastructure failures. Added 10 MB file size limit and 413 status code to `POST /upload`. |
| v4      | 2026-04-24 | Aligned contract with current implementation. `/ingest` and `/upload` responses now document `report_id` (integer \| null) and `warning` (string, optional). Clarified that `/ingest` AI analysis runs synchronously with typical 5–30s latency. Documented current `/upload` `batch_id: null` limitation pending follow-up fix. |

*Last updated: 2026-04-24*