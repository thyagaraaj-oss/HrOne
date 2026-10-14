from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.models.attendance import (
    AttendanceCorrectionRequest,
    AttendanceResponse,
    PunchInRequest,
    PunchOutRequest,
    PunchStatus,
)
from app.models.audit import AuditTrailResponse
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["Attendance"])


def get_attendance_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> AttendanceService:
    return AttendanceService(db)


@router.post(
    "/punch-in",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record employee punch-in",
    description="Registers shift start. Prevents duplicate active punches if an existing punch has not been closed.",
)
async def punch_in(
    payload: PunchInRequest,
    service: AttendanceService = Depends(get_attendance_service),
) -> AttendanceResponse:
    return await service.punch_in(payload)


@router.post(
    "/punch-out",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Record employee punch-out",
    description="Registers shift completion, validates that punch-out time is not before punch-in, and computes total working hours.",
)
async def punch_out(
    payload: PunchOutRequest,
    service: AttendanceService = Depends(get_attendance_service),
) -> AttendanceResponse:
    return await service.punch_out(payload)


@router.put(
    "/{record_id}/correct",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Manual attendance correction with audit trail",
    description="Updates attendance records while producing an immutable, timestamped audit log detailing who modified what and why.",
)
async def correct_attendance(
    record_id: str,
    payload: AttendanceCorrectionRequest,
    service: AttendanceService = Depends(get_attendance_service),
) -> Dict[str, Any]:
    return await service.correct_attendance(record_id=record_id, payload=payload)


@router.get(
    "",
    response_model=List[AttendanceResponse],
    status_code=status.HTTP_200_OK,
    summary="List attendance records",
    description="Query attendance logs filtered by employee or status with pagination.",
)
async def list_attendance(
    employee_id: Optional[str] = Query(None, description="Filter by employee ID"),
    status: Optional[PunchStatus] = Query(None, description="Filter by status (ACTIVE / COMPLETED)"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    skip: int = Query(0, ge=0, description="Offset"),
    service: AttendanceService = Depends(get_attendance_service),
) -> List[AttendanceResponse]:
    return await service.list_records(
        employee_id=employee_id, status=status, limit=limit, skip=skip
    )


@router.get(
    "/audit-trail",
    response_model=List[AuditTrailResponse],
    status_code=status.HTTP_200_OK,
    summary="Query attendance audit trail",
    description="Retrieves immutable audit logs for attendance corrections.",
)
async def list_audit_trail(
    attendance_id: Optional[str] = Query(None, description="Filter audit logs by attendance record ID"),
    employee_id: Optional[str] = Query(None, description="Filter audit logs by employee ID"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    service: AttendanceService = Depends(get_attendance_service),
) -> List[AuditTrailResponse]:
    return await service.get_audit_trail(
        attendance_id=attendance_id, employee_id=employee_id, limit=limit
    )


@router.get(
    "/{record_id}",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single attendance record",
)
async def get_attendance_record(
    record_id: str,
    service: AttendanceService = Depends(get_attendance_service),
) -> AttendanceResponse:
    return await service.get_by_id(record_id)
