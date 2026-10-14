from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_punch_in_success(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={
            "employee_id": "EMP-001",
            "location": "Main Office - 4th Floor",
            "notes": "Arrived on time",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["employee_id"] == "EMP-001"
    assert data["status"] == "ACTIVE"
    assert data["punch_out"] is None
    assert data["working_hours"] is None
    assert data["is_corrected"] is False
    assert data["location"] == "Main Office - 4th Floor"
    assert "id" in data


@pytest.mark.asyncio
async def test_prevent_duplicate_active_punch_in(async_client: AsyncClient):
    # First punch in
    res1 = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-002"},
    )
    assert res1.status_code == 201

    # Second punch in before punching out must fail with 400
    res2 = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-002"},
    )
    assert res2.status_code == 400
    err = res2.json()
    assert err["error"] is True
    assert err["error_code"] == "DUPLICATE_ACTIVE_PUNCH"
    assert "Active punch session already exists" in err["message"]


@pytest.mark.asyncio
async def test_punch_out_success(async_client: AsyncClient):
    base_time = datetime(2026, 10, 14, 9, 0, 0, tzinfo=timezone.utc)
    out_time = datetime(2026, 10, 14, 17, 30, 0, tzinfo=timezone.utc)

    # Punch in at 09:00 UTC
    res_in = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-003", "timestamp": base_time.isoformat()},
    )
    assert res_in.status_code == 201

    # Punch out at 17:30 UTC (8.5 hours)
    res_out = await async_client.post(
        "/api/v1/attendance/punch-out",
        json={
            "employee_id": "EMP-003",
            "timestamp": out_time.isoformat(),
            "notes": "Completed end-of-day reports",
        },
    )
    assert res_out.status_code == 200
    data = response_data = res_out.json()
    assert data["employee_id"] == "EMP-003"
    assert data["status"] == "COMPLETED"
    assert data["working_hours"] == 8.5
    assert data["punch_out"] is not None


@pytest.mark.asyncio
async def test_punch_out_without_active_session_fails(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/attendance/punch-out",
        json={"employee_id": "EMP-NONEXISTENT"},
    )
    assert response.status_code == 404
    err = response.json()
    assert err["error"] is True
    assert err["error_code"] == "ACTIVE_PUNCH_NOT_FOUND"


@pytest.mark.asyncio
async def test_punch_out_before_punch_in_fails(async_client: AsyncClient):
    punch_in_time = datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc)
    invalid_out_time = datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc)

    # Punch in at 10:00
    await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-004", "timestamp": punch_in_time.isoformat()},
    )

    # Punch out at 08:00 (earlier than punch in)
    response = await async_client.post(
        "/api/v1/attendance/punch-out",
        json={
            "employee_id": "EMP-004",
            "timestamp": invalid_out_time.isoformat(),
        },
    )
    assert response.status_code == 400
    err = response.json()
    assert err["error"] is True
    assert err["error_code"] == "INVALID_TIMESTAMP_SEQUENCE"
    assert "cannot be earlier than punch-in" in err["message"]


@pytest.mark.asyncio
async def test_punch_in_validation_empty_id(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "   "},
    )
    assert response.status_code == 422
    err = response.json()
    assert err["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_multiple_sequential_shifts(async_client: AsyncClient):
    emp = "EMP-005"
    t1_in = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
    t1_out = datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc)
    t2_in = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
    t2_out = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)

    # Day 1
    r1 = await async_client.post(
        "/api/v1/attendance/punch-in", json={"employee_id": emp, "timestamp": t1_in.isoformat()}
    )
    assert r1.status_code == 201
    r2 = await async_client.post(
        "/api/v1/attendance/punch-out", json={"employee_id": emp, "timestamp": t1_out.isoformat()}
    )
    assert r2.status_code == 200
    assert r2.json()["working_hours"] == 8.0

    # Day 2
    r3 = await async_client.post(
        "/api/v1/attendance/punch-in", json={"employee_id": emp, "timestamp": t2_in.isoformat()}
    )
    assert r3.status_code == 201
    r4 = await async_client.post(
        "/api/v1/attendance/punch-out", json={"employee_id": emp, "timestamp": t2_out.isoformat()}
    )
    assert r4.status_code == 200
    assert r4.json()["working_hours"] == 9.0
