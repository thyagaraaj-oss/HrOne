from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, Field


class AuditTrailResponse(BaseModel):
    id: str = Field(..., description="Unique audit log identifier")
    attendance_id: str = Field(..., description="Referenced attendance record ID")
    employee_id: str = Field(..., description="Employee identifier")
    changed_by: str = Field(..., description="User or HR agent who executed the modification")
    reason: str = Field(..., description="Documented reason for attendance adjustment")
    previous_state: Dict[str, Any] = Field(..., description="Snapshot of fields prior to modification")
    new_state: Dict[str, Any] = Field(..., description="Snapshot of modified fields")
    timestamp: datetime = Field(..., description="Immutable UTC timestamp when modification was logged")
