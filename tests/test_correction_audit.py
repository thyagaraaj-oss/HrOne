from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_manual_correction_and_audit_trail(async_client: AsyncClient):
    # 1. Create a base shift (Active)
    t_in = datetime(2026, 10, 14, 9, 0, 0, tzinfo=timezone.utc)
    res_in = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-AUDIT-1", "timestamp": t_in.isoformat()},
    )
    assert res_in.status_code == 201
    record = res_in.json()
    record_id = record["id"]

    # 2. Apply manual correction to supply missing punch_out
    t_corrected_out = datetime(2026, 10, 14, 18, 0, 0, tzinfo=timezone.utc)
    res_correct = await async_client.put(
        f"/api/v1/attendance/{record_id}/correct",
        json={
            "changed_by": "HR-MANAGER-SMITH",
            "reason": "Employee had an emergency and could not punch out at turnstile.",
            "punch_out": t_corrected_out.isoformat(),
        },
    )
    assert res_correct.status_code == 200
    corr_data = res_correct.json()

    # Verify updated attendance state
    att = corr_data["attendance"]
    assert att["id"] == record_id
    assert att["status"] == "COMPLETED"
    assert att["working_hours"] == 9.0
    assert att["is_corrected"] is True
    assert att["correction_count"] == 1

    # Verify audit trail contents
    audit = corr_data["audit_trail"]
    assert audit["attendance_id"] == record_id
    assert audit["employee_id"] == "EMP-AUDIT-1"
    assert audit["changed_by"] == "HR-MANAGER-SMITH"
    assert "emergency" in audit["reason"]
    assert audit["previous_state"]["punch_out"] is None
    assert audit["new_state"]["punch_out"] is not None
    assert audit["new_state"]["working_hours"] == 9.0
    assert "timestamp" in audit


@pytest.mark.asyncio
async def test_correction_with_invalid_timestamp_order(async_client: AsyncClient):
    t_in = datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc)
    res = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": "EMP-AUDIT-2", "timestamp": t_in.isoformat()},
    )
    record_id = res.json()["id"]

    # Attempt to set punch_out earlier than punch_in
    invalid_out = datetime(2026, 10, 14, 7, 0, 0, tzinfo=timezone.utc)
    res_err = await async_client.put(
        f"/api/v1/attendance/{record_id}/correct",
        json={
            "changed_by": "HR-ADMIN",
            "reason": "Correction test with invalid timestamp",
            "punch_out": invalid_out.isoformat(),
        },
    )
    assert res_err.status_code == 400
    err = res_err.json()
    assert err["error_code"] == "INVALID_CORRECTION"
    assert "cannot be before punch-in" in err["message"]


@pytest.mark.asyncio
async def test_correction_nonexistent_record_returns_404(async_client: AsyncClient):
    res = await async_client.put(
        "/api/v1/attendance/507f1f77bcf86cd799439011/correct",
        json={
            "changed_by": "HR-ADMIN",
            "reason": "Testing nonexistent record",
            "punch_out": datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert res.status_code == 404
    err = res.json()
    assert err["error_code"] == "RECORD_NOT_FOUND"


@pytest.mark.asyncio
async def test_query_audit_trail_endpoint(async_client: AsyncClient):
    emp = "EMP-AUDIT-MULTI"
    t_in = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    res_in = await async_client.post(
        "/api/v1/attendance/punch-in",
        json={"employee_id": emp, "timestamp": t_in.isoformat()},
    )
    rec_id = res_in.json()["id"]

    # First correction
    await async_client.put(
        f"/api/v1/attendance/{rec_id}/correct",
        json={
            "changed_by": "SUPERVISOR-A",
            "reason": "First manual correction entry",
            "punch_out": datetime(2026, 10, 12, 17, 0, tzinfo=timezone.utc).isoformat(),
        },
    )

    # Second correction adjusting punch_in
    await async_client.put(
        f"/api/v1/attendance/{rec_id}/correct",
        json={
            "changed_by": "SUPERVISOR-B",
            "reason": "Adjusting punch-in due to badge scanner desync",
            "punch_in": datetime(2026, 10, 12, 8, 30, tzinfo=timezone.utc).isoformat(),
        },
    )

    # Query audit logs
    res_audit = await async_client.get(
        f"/api/v1/attendance/audit-trail?employee_id={emp}"
    )
    assert res_audit.status_code == 200
    audits = res_audit.json()
    assert len(audits) == 2
    # Verify latest audit is first (timestamp -1)
    assert audits[0]["changed_by"] == "SUPERVISOR-B"
    assert audits[1]["changed_by"] == "SUPERVISOR-A"
