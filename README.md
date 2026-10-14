# HROne Employee Attendance & Analytics API

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![MongoDB Motor](https://img.shields.io/badge/MongoDB-Motor%203.6+-green.svg)](https://motor.readthedocs.io/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.8+-e92063.svg)](https://docs.pydantic.dev/)
[![Tests](https://img.shields.io/badge/Tests-14%20Passed-brightgreen.svg)]()

Production-grade, asynchronous REST API microservice for employee attendance management, manual corrections with an immutable audit trail, and high-performance workforce analytics powered by native MongoDB aggregation pipelines.

---

## Table of Contents
- [Key Features](#key-features)
- [Project Architecture](#project-architecture)
- [Prerequisites](#prerequisites)
- [Local Setup & Installation](#local-setup--installation)
- [Running the Application](#running-the-application)
- [API Documentation & Endpoints](#api-documentation--endpoints)
  - [1. Punch-In](#1-punch-in)
  - [2. Punch-Out](#2-punch-out)
  - [3. Attendance Correction & Audit Trail](#3-attendance-correction--audit-trail)
  - [4. Query Attendance Records](#4-query-attendance-records)
  - [5. Query Audit Trail](#5-query-audit-trail)
  - [6. Workforce Analytics (Aggregation Pipelines)](#6-workforce-analytics-aggregation-pipelines)
  - [7. Organization Summary Analytics](#7-organization-summary-analytics)
- [Running Automated Tests](#running-automated-tests)
- [Configuration Reference](#configuration-reference)
- [Architecture & Design Documentation](#architecture--design-documentation)

---

## Key Features

1. **Shift Lifecycle & Business Validation:**
   - Strict validation preventing duplicate active punches without an intervening punch-out.
   - Database-level unique partial filter index enforcing non-duplication across concurrent requests.
   - Automatic chronological sequence verification (punch-out timestamp cannot precede punch-in).
   - Dynamic shift duration and productive working hours calculation rounded to 2 decimal places.

2. **Immutable Audit Trail:**
   - Dedicated `attendance_audits` collection recording complete change history.
   - Tracks `changed_by`, `reason`, `previous_state`, `new_state`, and immutable UTC timestamps.
   - Automatically increments record `correction_count` and updates status flags.

3. **High-Performance MongoDB Aggregation Pipelines:**
   - Executes aggregation stages (`$match`, `$project`, `$group`, `$sort`) directly within MongoDB.
   - Computes total working hours, average shift durations, total shifts completed, and correction counts grouped by employee.
   - Supports optional date filtering (`start_date`, `end_date`) and single-employee queries.

4. **Standards-Compliant Error Handling:**
   - Replaces generic 500 errors with explicit HTTP status codes (`400`, `404`, `422`).
   - Structured JSON error envelopes detailing error codes, messages, and parameter-level validation details.

---

## Project Architecture

```
HrOne/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application, lifespan & exception handlers
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic Settings & environment config
│   │   ├── database.py          # Motor connection manager & MongoDB index creation
│   │   └── exceptions.py        # Domain exception hierarchy (400, 404, 422)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── attendance.py        # Attendance request/response Pydantic models
│   │   ├── audit.py             # Audit trail schema
│   │   └── analytics.py         # Workforce analytics metric models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── attendance.py        # Endpoints: /punch-in, /punch-out, /correct, /audit-trail
│   │   └── analytics.py         # Endpoints: /analytics/employees, /analytics/summary
│   └── services/
│       ├── __init__.py
│       ├── attendance_service.py# Shift lifecycle, validations & audit logging
│       └── analytics_service.py # Native MongoDB aggregation pipelines
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # In-memory mongomock fixtures & AsyncClient setup
│   ├── test_attendance.py       # Punch-in/out and sequence validation tests
│   ├── test_correction_audit.py # Manual corrections & audit trail tests
│   └── test_analytics.py        # Aggregation pipeline analytics tests
├── DECISIONS.md                 # Architectural Decision Records (ADRs)
├── REVIEW.md                    # Code review, security & scalability analysis
├── pytest.ini                   # Pytest configuration
├── requirements.txt             # Pinned production and test dependencies
└── .gitignore                   # Standard production git exclusions
```

---

## Prerequisites

- **Python:** 3.12+ (or 3.10+)
- **MongoDB:** Community or Enterprise Server 4.4+ (or MongoDB Atlas)

---

## Local Setup & Installation

### 1. Clone the repository and navigate to the directory:
```bash
git clone https://github.com/thyagaraaj-oss/HrOne.git
cd HrOne
```

### 2. Activate Python Virtual Environment:
```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies:
```bash
pip install -r requirements.txt
```

---

## Running the Application

### 1. Ensure MongoDB is running:
If running MongoDB locally on default port `27017`:
```bash
# Example for local MongoDB instance
mongod --dbpath ./data/db
```
*(If using MongoDB Atlas or a remote instance, set the `MONGODB_URL` environment variable.)*

### 2. Start the FastAPI Development Server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Access Interactive API Documentation:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## API Documentation & Endpoints

All core API endpoints are prefixed with `/api/v1`.

### 1. Punch-In
Registers shift start for an employee.

- **URL:** `POST /api/v1/attendance/punch-in`
- **Status Code:** `201 Created` (or `400 Bad Request` if an active punch already exists)

**Request Body:**
```json
{
  "employee_id": "EMP-1001",
  "location": "Headquarters - 3rd Floor",
  "notes": "Starting morning shift"
}
```

**Response (201 Created):**
```json
{
  "id": "670da4187e14dcf7a1bc8190",
  "employee_id": "EMP-1001",
  "punch_in": "2026-10-14T09:00:00Z",
  "punch_out": null,
  "working_hours": null,
  "status": "ACTIVE",
  "is_corrected": false,
  "correction_count": 0,
  "location": "Headquarters - 3rd Floor",
  "notes": "Starting morning shift",
  "created_at": "2026-10-14T09:00:00Z",
  "updated_at": "2026-10-14T09:00:00Z"
}
```

---

### 2. Punch-Out
Registers shift completion, validates timestamps, and computes total working hours.

- **URL:** `POST /api/v1/attendance/punch-out`
- **Status Code:** `200 OK` (or `404 Not Found` if no active session, `400 Bad Request` if timestamp precedes punch-in)

**Request Body:**
```json
{
  "employee_id": "EMP-1001",
  "notes": "Completed deliverables"
}
```

**Response (200 OK):**
```json
{
  "id": "670da4187e14dcf7a1bc8190",
  "employee_id": "EMP-1001",
  "punch_in": "2026-10-14T09:00:00Z",
  "punch_out": "2026-10-14T17:30:00Z",
  "working_hours": 8.5,
  "status": "COMPLETED",
  "is_corrected": false,
  "correction_count": 0,
  "location": "Headquarters - 3rd Floor",
  "notes": "Starting morning shift | Completed deliverables",
  "created_at": "2026-10-14T09:00:00Z",
  "updated_at": "2026-10-14T17:30:00Z"
}
```

---

### 3. Attendance Correction & Audit Trail
Allows HR managers to adjust timestamps or status while generating an immutable audit record.

- **URL:** `PUT /api/v1/attendance/{record_id}/correct`
- **Status Code:** `200 OK` (or `400 Bad Request`, `404 Not Found`)

**Request Body:**
```json
{
  "changed_by": "HR-MANAGER-SMITH",
  "reason": "Employee forgot to punch out due to client meeting offsite.",
  "punch_out": "2026-10-14T18:00:00Z"
}
```

**Response (200 OK):**
```json
{
  "attendance": {
    "id": "670da4187e14dcf7a1bc8190",
    "employee_id": "EMP-1001",
    "punch_in": "2026-10-14T09:00:00Z",
    "punch_out": "2026-10-14T18:00:00Z",
    "working_hours": 9.0,
    "status": "COMPLETED",
    "is_corrected": true,
    "correction_count": 1,
    "location": "Headquarters - 3rd Floor",
    "notes": "Starting morning shift",
    "created_at": "2026-10-14T09:00:00Z",
    "updated_at": "2026-10-14T18:05:00Z"
  },
  "audit_trail": {
    "id": "670da4187e14dcf7a1bc8191",
    "attendance_id": "670da4187e14dcf7a1bc8190",
    "employee_id": "EMP-1001",
    "changed_by": "HR-MANAGER-SMITH",
    "reason": "Employee forgot to punch out due to client meeting offsite.",
    "previous_state": {
      "punch_in": "2026-10-14T09:00:00+00:00",
      "punch_out": null,
      "working_hours": null,
      "status": "ACTIVE"
    },
    "new_state": {
      "punch_in": "2026-10-14T09:00:00+00:00",
      "punch_out": "2026-10-14T18:00:00+00:00",
      "working_hours": 9.0,
      "status": "COMPLETED"
    },
    "timestamp": "2026-10-14T18:05:00Z"
  }
}
```

---

### 4. Query Attendance Records
- **URL:** `GET /api/v1/attendance`
- **Query Parameters:**
  - `employee_id` (optional): Filter by specific employee
  - `status` (optional): `ACTIVE` or `COMPLETED`
  - `limit` (default: 50): Page size (1 to 200)
  - `skip` (default: 0): Pagination offset

---

### 5. Query Audit Trail
- **URL:** `GET /api/v1/attendance/audit-trail`
- **Query Parameters:**
  - `attendance_id` (optional): Filter audit logs by attendance document ID
  - `employee_id` (optional): Filter audit logs by employee ID
  - `limit` (default: 50): Page size

---

### 6. Workforce Analytics (Aggregation Pipelines)
Executes a native MongoDB pipeline grouping completed shifts by employee.

- **URL:** `GET /api/v1/analytics/employees`
- **Query Parameters:**
  - `employee_id` (optional): Filter for a single employee
  - `start_date` (optional): ISO format start date (e.g. `2026-10-01T00:00:00Z`)
  - `end_date` (optional): ISO format end date (e.g. `2026-10-31T23:59:59Z`)

**Response (200 OK):**
```json
[
  {
    "employee_id": "EMP-1001",
    "total_working_hours": 168.5,
    "average_shift_duration": 8.42,
    "total_shifts": 20,
    "total_corrections": 1
  },
  {
    "employee_id": "EMP-1002",
    "total_working_hours": 152.0,
    "average_shift_duration": 8.0,
    "total_shifts": 19,
    "total_corrections": 0
  }
]
```

---

### 7. Organization Summary Analytics
Aggregates grand totals across the entire organization alongside employee-level breakdowns.

- **URL:** `GET /api/v1/analytics/summary`

**Response (200 OK):**
```json
{
  "total_employees_analyzed": 2,
  "total_working_hours": 320.5,
  "overall_average_shift_duration": 8.22,
  "total_shifts_completed": 39,
  "total_corrections_logged": 1,
  "employees": [ ... ]
}
```

---

## Running Automated Tests

The test suite runs with Pytest and `mongomock-motor`. It executes completely in-memory without requiring a running MongoDB instance:

```bash
# Run all tests with standard verbose output
pytest

# Run tests with detailed short tracebacks
pytest -v --tb=short
```

### Test Coverage Highlights:
- **`test_attendance.py`**:
  - `test_punch_in_success`: Validates document creation, status, and IDs.
  - `test_prevent_duplicate_active_punch_in`: Verifies 400 error on duplicate active punch.
  - `test_punch_out_success`: Validates working hours calculation.
  - `test_punch_out_without_active_session_fails`: Verifies 404 response.
  - `test_punch_out_before_punch_in_fails`: Validates timestamp chronology (400).
  - `test_punch_in_validation_empty_id`: Verifies input validation failure (422).
  - `test_multiple_sequential_shifts`: Verifies multi-day sequential punch lifecycles.
- **`test_correction_audit.py`**:
  - `test_manual_correction_and_audit_trail`: Verifies previous/new state capture and audit immutability.
  - `test_correction_with_invalid_timestamp_order`: Verifies chronology check on corrections (400).
  - `test_correction_nonexistent_record_returns_404`: Verifies 404 handling.
  - `test_query_audit_trail_endpoint`: Verifies timestamp-ordered audit log retrieval.
- **`test_analytics.py`**:
  - `test_native_mongodb_analytics_pipeline`: Validates `$match`, `$project`, `$group`, `$sort` calculations.
  - `test_single_employee_analytics_endpoint`: Verifies single-employee analytics.
  - `test_organization_summary_analytics`: Verifies organization-wide rolled-up totals.

---

## Configuration Reference

The service can be configured via environment variables:

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection URI string |
| `DATABASE_NAME` | `hrone_attendance` | Target database name |
| `ATTENDANCE_COLLECTION` | `attendance_records` | Primary collection for shift documents |
| `AUDIT_COLLECTION` | `attendance_audits` | Append-only collection for correction audit logs |
| `DEBUG` | `False` | Debug mode toggle |

---

## Architecture & Design Documentation

For in-depth architectural and code review discussions, refer to:
- [`DECISIONS.md`](file:///c:/Users/nothing/HrOne/DECISIONS.md): Architectural Decision Records (ADRs), data modeling trade-offs, and MongoDB index strategy.
- [`REVIEW.md`](file:///c:/Users/nothing/HrOne/REVIEW.md): Code review, security considerations, bottleneck analysis, and horizontal scalability recommendations.
