from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class EmployeeAnalyticsMetric(BaseModel):
    employee_id: str = Field(..., description="Unique employee identifier")
    total_working_hours: float = Field(
        ..., description="Cumulative completed working hours for the selected period"
    )
    average_shift_duration: float = Field(
        ..., description="Average duration of completed shifts in hours"
    )
    total_shifts: int = Field(..., description="Total number of completed shifts logged")
    total_corrections: int = Field(
        ..., description="Total manual corrections applied across employee shifts"
    )


class AnalyticsSummaryResponse(BaseModel):
    total_employees_analyzed: int = Field(
        ..., description="Number of unique employees with completed shifts"
    )
    total_working_hours: float = Field(
        ..., description="Grand total working hours across all selected employees"
    )
    overall_average_shift_duration: float = Field(
        ..., description="Average shift duration across all completed shifts"
    )
    total_shifts_completed: int = Field(
        ..., description="Total completed shifts across all selected employees"
    )
    total_corrections_logged: int = Field(
        ..., description="Total manual corrections logged across all analyzed records"
    )
    employees: List[EmployeeAnalyticsMetric] = Field(
        default_factory=list, description="Per-employee metrics breakdown"
    )
