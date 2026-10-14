# Architectural & Technical Decision Records (ADR)
## HROne Employee Attendance & Analytics API

---

### 1. Executive Summary

The **HROne Employee Attendance & Analytics API** is designed as a high-throughput, horizontally scalable, and resilient enterprise microservice. Its primary responsibilities are tracking employee shift lifecycles (punch-in, punch-out), preserving a non-repudiable audit trail for manual corrections, and delivering real-time workforce analytics via native MongoDB aggregation pipelines.

This document formalizes the architectural decisions, data modeling patterns, technology choices, and indexing strategies governing the implementation.

---

### 2. Technology Stack Selection & Rationale

| Layer / Concern | Chosen Technology | Evaluated Alternatives | Rationale & Justification |
| :--- | :--- | :--- | :--- |
| **Language & Runtime** | **Python 3.12 (Asyncio)** | Node.js, Go, Python 3.10 | Python 3.12 delivers significant performance improvements (specializing adaptive interpreter, sub-interpreters, faster exception handling) and a mature ecosystem for data modeling and enterprise backend services. |
| **Web Framework** | **FastAPI** | Flask, Django, Starlette (raw) | Asynchronous-first (ASGI), automatic OpenAPI/Swagger generation, dependency injection container, and native integration with Pydantic v2. |
| **Data Validation** | **Pydantic v2** | Marshmallow, Cerberus, Pydantic v1 | Pydantic v2 is re-architected in Rust (`pydantic-core`), delivering a 5x to 20x performance improvement in data parsing, serialization, and strict type validation. |
| **Database Driver** | **Motor (`AsyncIOMotorClient`)** | PyMongo, MongoEngine, Beanie | Motor is the official async driver wrapping PyMongo for `asyncio`. It avoids thread-blocking calls during I/O operations, allowing single worker processes to handle thousands of concurrent client connections. |
| **Testing Harness** | **Pytest + `mongomock-motor` + HTTPX** | Unittest, live MongoDB container | Eliminates external daemon dependencies for CI/CD runs. Tests run in under 500ms in an isolated in-memory event loop while executing genuine async MongoDB queries and aggregation pipelines. |

---

### 3. Data Modeling Decisions & Trade-Offs

#### 3.1 Session-Oriented Document vs. Event Sourcing
* **Pattern Chosen:** **Session-Oriented Attendance Document** (with an associated immutable audit trail).
* **Alternative Considered:** Pure Event Sourcing (logging only raw "PUNCH_IN" and "PUNCH_OUT" events as independent rows).
* **Trade-Off Analysis:**
  - *Event Sourcing Pros:* Infinite append-only logs; simple write path.
  - *Event Sourcing Cons:* Computing current status, active punch state, and shift duration requires resolving state across sequential records on every read or running complex map-reduce/window functions.
  - *Session-Oriented Pros:* Direct O(1) query for active shifts (`punch_out: null`); immediate availability of `working_hours` and `status`; simplifies turnstile and biometric device integration.
  - *Decision:* A session document represents the core attendance unit (`punch_in`, `punch_out`, `working_hours`, `status`). All modifications trigger writes to an immutable `attendance_audits` collection, preserving strict audit compliance without sacrificing query speed.

#### 3.2 Audit Trail Architecture: Separate Collection vs. Embedded Array
* **Pattern Chosen:** **Dedicated `attendance_audits` Collection**.
* **Alternative Considered:** Embedding a `history: [...]` array directly inside the attendance record document.
* **Trade-Off Analysis:**
  - *Embedded Array:* Risks document growth and memory reallocation in MongoDB if records undergo repeated revisions (approaching the 16MB document limit in extreme edge cases). Furthermore, compliance teams require separate access controls on audit collections.
  - *Dedicated Collection:* Fully immutable and append-only. Can be secured with strict database write-only or insert-only access privileges. Indexes on `(attendance_id, timestamp)` and `(employee_id, timestamp)` make cross-organization audit reports efficient.

---

### 4. MongoDB Indexing Strategy

To guarantee strict business rules and sub-millisecond query execution at enterprise scale (100,000+ employees), the following indexes are provisioned on application startup:

#### 4.1 Unique Partial Filter Index (Duplicate Active Punch Prevention)
```javascript
db.attendance_records.createIndex(
  { "employee_id": 1 },
  { 
    unique: true, 
    partialFilterExpression: { "punch_out": null },
    name: "idx_unique_active_punch_per_employee"
  }
)
```
* **Why it matters:** Application-level validation (`find_one` then `insert_one`) suffers from **race conditions** when two concurrent requests arrive simultaneously (e.g., dual card swipe on synchronized readers).
* **Engine-Level Guarantee:** The MongoDB unique partial index guarantees that no more than one document per `employee_id` can ever have `punch_out: null`. Any competing concurrent insert immediately triggers a `DuplicateKeyError` (E11000), which the application intercepts and transforms into an HTTP 400 response.

#### 4.2 Compound Timeline Index
```javascript
db.attendance_records.createIndex(
  { "employee_id": 1, "punch_in": -1 },
  { name: "idx_employee_punch_in_desc" }
)
```
* Supports pagination and rapid retrieval of an employee's historical shift logs ordered chronologically.

#### 4.3 Composite Analytics Index
```javascript
db.attendance_records.createIndex(
  { "status": 1, "punch_in": 1, "employee_id": 1 },
  { name: "idx_status_punchin_employee" }
)
```
* Powers the native aggregation pipeline by allowing the `$match` stage on `status: "COMPLETED"` and date boundaries to perform an Index Scan (`IXSCAN`) rather than a Collection Scan (`COLLSCAN`).

#### 4.4 Audit Trail Indexes
```javascript
db.attendance_audits.createIndex(
  { "attendance_id": 1, "timestamp": -1 },
  { name: "idx_audit_attendance_time" }
)
db.attendance_audits.createIndex(
  { "employee_id": 1, "timestamp": -1 },
  { name: "idx_audit_employee_time" }
)
```
* Guarantees rapid lookup of audit trails by either record ID or employee identifier.

---

### 5. Native Aggregation Pipeline Design

Rather than pulling millions of attendance documents into Python memory to compute sums and averages, analytics are computed directly in the MongoDB storage engine using native aggregation pipelines:

```javascript
[
  // 1. Filter completed shifts within date window
  {
    $match: {
      status: "COMPLETED",
      punch_in: { $ne: null },
      punch_out: { $ne: null }
      // (optional date range criteria applied here)
    }
  },
  // 2. Project working_hours (with fallback calculation) and correction counts
  {
    $project: {
      employee_id: 1,
      working_hours: {
        $ifNull: [
          "$working_hours",
          { $divide: [{ $subtract: ["$punch_out", "$punch_in"] }, 3600000.0] }
        ]
      },
      correction_count: { $ifNull: ["$correction_count", 0] }
    }
  },
  // 3. Group by employee and aggregate key metrics
  {
    $group: {
      _id: "$employee_id",
      total_working_hours: { $sum: "$working_hours" },
      average_shift_duration: { $avg: "$working_hours" },
      total_shifts: { $sum: 1 },
      total_corrections: { $sum: "$correction_count" }
    }
  },
  // 4. Project clean presentation fields
  {
    $project: {
      _id: 0,
      employee_id: "$_id",
      total_working_hours: "$total_working_hours",
      average_shift_duration: "$average_shift_duration",
      total_shifts: 1,
      total_corrections: 1
    }
  },
  // 5. Rank employees by total productive hours
  { $sort: { total_working_hours: -1 } }
]
```

**Benefits:**
- **Zero Memory Bottlenecks in Python:** MongoDB computes sums and averages in C++ engine memory with optimized paging.
- **Index-Backed Filtering:** Utilizes `idx_status_punchin_employee`.
- **Portability:** Fully compatible with standard MongoDB 4.x - 7.x clusters and document databases.

---

### 6. Error Handling & HTTP Status Code Specification

The API replaces generic 500 server errors with explicit HTTP status codes conforming to RFC 9110:

| Scenario | HTTP Status | Code / Identifier | User-Facing Message |
| :--- | :--- | :--- | :--- |
| **Punch-in created successfully** | `201 Created` | - | Full attendance session document returned. |
| **Duplicate active punch attempt** | `400 Bad Request` | `DUPLICATE_ACTIVE_PUNCH` | "Active punch session already exists for employee... Punch-out required before punching in again." |
| **Punch-out without prior punch-in**| `404 Not Found` | `ACTIVE_PUNCH_NOT_FOUND` | "No active punch-in session found for employee..." |
| **Punch-out timestamp precedes punch-in** | `400 Bad Request` | `INVALID_TIMESTAMP_SEQUENCE`| "Punch-out time cannot be earlier than punch-in time." |
| **Attendance record not found** | `404 Not Found` | `RECORD_NOT_FOUND` | "Attendance record with ID '...' not found." |
| **Invalid correction payload** | `400 Bad Request` | `INVALID_CORRECTION` | "Corrected punch-out cannot be before punch-in." |
| **Validation failure (schema/format)** | `422 Unprocessable Content`| `VALIDATION_ERROR` | Detailed JSON breakdown identifying invalid fields. |
