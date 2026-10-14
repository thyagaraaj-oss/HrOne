from typing import Any, Optional
from fastapi import HTTPException, status


class AttendanceException(HTTPException):
    """Base exception for Attendance domain errors."""

    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: str = "Attendance business rule violation",
        error_code: str = "ATTENDANCE_ERROR",
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra = extra or {}


class DuplicateActivePunchException(AttendanceException):
    def __init__(
        self,
        employee_id: str,
        active_record_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Active punch session already exists for employee '{employee_id}'. A punch-out is required before punching in again.",
            error_code="DUPLICATE_ACTIVE_PUNCH",
            extra={"employee_id": employee_id, "active_record_id": active_record_id},
        )


class ActivePunchNotFoundException(AttendanceException):
    def __init__(self, employee_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active punch-in session found for employee '{employee_id}'. Cannot punch out.",
            error_code="ACTIVE_PUNCH_NOT_FOUND",
            extra={"employee_id": employee_id},
        )


class AttendanceRecordNotFoundException(AttendanceException):
    def __init__(self, record_id: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance record with ID '{record_id}' not found.",
            error_code="RECORD_NOT_FOUND",
            extra={"record_id": record_id},
        )


class InvalidPunchTimestampException(AttendanceException):
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="INVALID_TIMESTAMP_SEQUENCE",
        )


class InvalidCorrectionException(AttendanceException):
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="INVALID_CORRECTION",
        )
