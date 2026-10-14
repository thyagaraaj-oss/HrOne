from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class PunchStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class PunchInRequest(BaseModel):
    employee_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique employee identifier",
        examples=["EMP-1001"],
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional explicit punch-in timestamp in UTC. Defaults to current time if omitted.",
    )
    location: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Physical office, branch, or GPS location",
        examples=["Headquarters - Building A"],
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional employee notes",
    )

    @field_validator("employee_id")
    @classmethod
    def validate_employee_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("employee_id cannot be empty or whitespace only.")
        return clean


class PunchOutRequest(BaseModel):
    employee_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique employee identifier",
        examples=["EMP-1001"],
    )
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Optional explicit punch-out timestamp in UTC. Defaults to current time if omitted.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional sign-out notes",
    )

    @field_validator("employee_id")
    @classmethod
    def validate_employee_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("employee_id cannot be empty or whitespace only.")
        return clean


class AttendanceCorrectionRequest(BaseModel):
    changed_by: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Identifier of the HR manager or administrator making the correction",
        examples=["HR-ADMIN-01"],
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Detailed reason justifying the manual adjustment",
        examples=["Employee forgot to punch out due to client meeting offsite."],
    )
    punch_in: Optional[datetime] = Field(
        default=None,
        description="Corrected punch-in timestamp (UTC)",
    )
    punch_out: Optional[datetime] = Field(
        default=None,
        description="Corrected punch-out timestamp (UTC)",
    )
    status: Optional[PunchStatus] = Field(
        default=None,
        description="Explicit status override (ACTIVE or COMPLETED)",
    )

    @field_validator("changed_by", "reason")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty or whitespace only.")
        return clean

    @model_validator(mode="after")
    def validate_at_least_one_change(self) -> "AttendanceCorrectionRequest":
        if self.punch_in is None and self.punch_out is None and self.status is None:
            raise ValueError(
                "Correction request must specify at least one field to change ('punch_in', 'punch_out', or 'status')."
            )
        if self.punch_in and self.punch_out and self.punch_out < self.punch_in:
            raise ValueError("Corrected punch_out cannot be earlier than punch_in.")
        return self


class AttendanceResponse(BaseModel):
    id: str = Field(..., description="Unique record identifier")
    employee_id: str = Field(..., description="Employee identifier")
    punch_in: datetime = Field(..., description="Timestamp when shift started")
    punch_out: Optional[datetime] = Field(
        default=None, description="Timestamp when shift ended, or null if active"
    )
    working_hours: Optional[float] = Field(
        default=None, description="Computed working duration in hours rounded to 2 decimals"
    )
    status: PunchStatus = Field(..., description="Status of the attendance entry")
    is_corrected: bool = Field(
        default=False, description="Whether this record has undergone manual adjustment"
    )
    correction_count: int = Field(
        default=0, description="Total number of corrections applied to this record"
    )
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
