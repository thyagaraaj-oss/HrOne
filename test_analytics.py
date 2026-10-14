from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_native_mongodb_analytics_pipeline(async_client: AsyncClient):
    # Setup shifts for Employee A: Shift 1 = 8 hours, Shift 2 = 10 hours (Total = 18 hrs, Avg = 9 hrs)
    # Day 1: 08:00 -> 16:00 (8h)
    await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-AN-A", "timestamp": datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc).isoformat()},
    )
    await async_client.post(
        "/api/v1/attendance/punch-out",
        json={"employee_id": "EMP-AN-A", "timestamp": datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc).isoformat()},
    )

    # Day 2: 08:00 -> 18:00 (10h)
    await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-AN-A", "timestamp": datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc).isoformat()},
    )
    await async_client.post(
        "/api/v1/attendance/punch-out",
        json={"employee_id": "EMP-AN-A", "timestamp": datetime(2026, 10, 2, 18, 0, tzinfo=timezone.utc).isoformat()},
    )

    # Setup shift for Employee B: 09:00 -> 15:00 (6h)
    res_b = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-AN-B", "timestamp": datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc).isoformat()},
    )
    await async_client.post(
        "/api/v1/attendance/punch-out",
        json={"employee_id": "EMP-AN-B", "timestamp": datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc).isoformat()},
    )

    # Add a correction to Employee B's shift
    rec_b_id = res_b.json()["id"]
    await async_client.put(
        f"/api/v1/attendance/{rec_b_id}/correct",
        json={
            "changed_by": "HR-LEAD",
            "reason": "Adding 1 hour approved overtime",
            "punch_out": datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc).isoformat(),
        },
    )

    # 1. Fetch Analytics for all employees
    res_analytics = await async_client.get("/api/v1/analytics/employees")
    assert res_analytics.status_code == 200
    metrics = res_analytics.json()
    assert len(metrics) >= 2

    # Verify EMP-AN-A (18 hours, 2 shifts, 9.0 avg, 0 corrections)
    emp_a_stat = next(m for m in metrics if m["employee_id"] == "EMP-AN-A")
    assert emp_a_stat["total_working_hours"] == 18.0
    assert emp_a_stat["average_shift_duration"] == 9.0
    assert emp_a_stat["total_shifts"] == 2
    assert emp_a_stat["total_corrections"] == 0

    # Verify EMP-AN-B (corrected to 7 hours: 09:00 to 16:00, 1 shift, 1 correction)
    emp_b_stat = next(m for m in metrics if m["employee_id"] == "EMP-AN-B")
    assert emp_b_stat["total_working_hours"] == 7.0
    assert emp_b_stat["average_shift_duration"] == 7.0
    assert emp_b_stat["total_shifts"] == 1
    assert emp_b_stat["total_corrections"] == 1


@pytest.mark.asyncio
async def test_single_employee_analytics_endpoint(async_client: AsyncClient):
    emp = "EMP-SINGLE"
    await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": emp, "timestamp": datetime(2026, 10, 5, 8, 30, tzinfo=timezone.utc).isoformat()},
    )
    await async_client.post(
        "/api/v1/attendance/punch-out",
        json={"employee_id": emp, "timestamp": datetime(2026, 10, 5, 17, 0, tzinfo=timezone.utc).isoformat()},
    )

    res = await async_client.get(f"/api/v1/analytics/employees/{emp}")
    assert res.status_code == 200
    data = res.json()
    assert data["employee_id"] == emp
    assert data["total_working_hours"] == 8.5
    assert data["total_shifts"] == 1


@pytest.mark.asyncio
async def test_organization_summary_analytics(async_client: AsyncClient):
    res = await async_client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
    summary = res.json()
    assert "total_employees_analyzed" in summary
    assert "total_working_hours" in summary
    assert "overall_average_shift_duration" in summary
    assert "total_shifts_completed" in summary
    assert "total_corrections_logged" in summary
    assert isinstance(summary["employees"], list)
