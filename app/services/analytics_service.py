from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.models.analytics import AnalyticsSummaryResponse, EmployeeAnalyticsMetric
from app.models.attendance import PunchStatus


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class AnalyticsService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[settings.ATTENDANCE_COLLECTION]

    async def get_employee_analytics(
        self,
        employee_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[EmployeeAnalyticsMetric]:
        """
        Executes a native MongoDB aggregation pipeline to compute:
        - Total working hours per employee
        - Average shift duration per employee
        - Total shifts completed
        - Total manual corrections applied
        """
        match_criteria: Dict[str, Any] = {
            "status": PunchStatus.COMPLETED.value,
            "punch_in": {"$ne": None},
            "punch_out": {"$ne": None},
        }

        if employee_id:
            match_criteria["employee_id"] = employee_id

        date_filter: Dict[str, Any] = {}
        if start_date:
            date_filter["$gte"] = _to_utc(start_date)
        if end_date:
            date_filter["$lte"] = _to_utc(end_date)
        if date_filter:
            match_criteria["punch_in"] = date_filter

        pipeline = [
            {"$match": match_criteria},
            {
                "$project": {
                    "employee_id": 1,
                    # Fallback to computing hours from punch timestamps if working_hours is null
                    "working_hours": {
                        "$ifNull": [
                            "$working_hours",
                            {
                                "$divide": [
                                    {"$subtract": ["$punch_out", "$punch_in"]},
                                    3600000.0,
                                ]
                            },
                        ]
                    },
                    "correction_count": {"$ifNull": ["$correction_count", 0]},
                }
            },
            {
                "$group": {
                    "_id": "$employee_id",
                    "total_working_hours": {"$sum": "$working_hours"},
                    "average_shift_duration": {"$avg": "$working_hours"},
                    "total_shifts": {"$sum": 1},
                    "total_corrections": {"$sum": "$correction_count"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "employee_id": "$_id",
                    "total_working_hours": "$total_working_hours",
                    "average_shift_duration": "$average_shift_duration",
                    "total_shifts": 1,
                    "total_corrections": 1,
                }
            },
            {"$sort": {"total_working_hours": -1}},
        ]

        cursor = self.collection.aggregate(pipeline)
        raw_results = await cursor.to_list(length=None)

        return [
            EmployeeAnalyticsMetric(
                employee_id=r["employee_id"],
                total_working_hours=round(float(r.get("total_working_hours", 0.0)), 2),
                average_shift_duration=round(float(r.get("average_shift_duration", 0.0)), 2),
                total_shifts=int(r.get("total_shifts", 0)),
                total_corrections=int(r.get("total_corrections", 0)),
            )
            for r in raw_results
        ]

    async def get_organization_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AnalyticsSummaryResponse:
        """
        Computes aggregate metrics across all employees alongside the per-employee breakdown.
        """
        metrics = await self.get_employee_analytics(
            employee_id=None,
            start_date=start_date,
            end_date=end_date,
        )

        total_employees = len(metrics)
        total_hours = round(sum(m.total_working_hours for m in metrics), 2)
        total_shifts = sum(m.total_shifts for m in metrics)
        total_corrections = sum(m.total_corrections for m in metrics)
        overall_avg = (
            round(total_hours / total_shifts, 2) if total_shifts > 0 else 0.0
        )

        return AnalyticsSummaryResponse(
            total_employees_analyzed=total_employees,
            total_working_hours=total_hours,
            overall_average_shift_duration=overall_avg,
            total_shifts_completed=total_shifts,
            total_corrections_logged=total_corrections,
            employees=metrics,
        )
