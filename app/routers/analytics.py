from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_db
from app.models.analytics import AnalyticsSummaryResponse, EmployeeAnalyticsMetric
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_analytics_service(db: AsyncIOMotorDatabase = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


@router.get(
    "/employees",
    response_model=List[EmployeeAnalyticsMetric],
    status_code=status.HTTP_200_OK,
    summary="Employee attendance analytics",
    description="Uses native MongoDB aggregation pipelines to calculate total working hours, average shift duration, total shifts logged, and correction counts grouped by employee.",
)
async def get_employee_analytics(
    employee_id: Optional[str] = Query(None, description="Optional employee filter"),
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> List[EmployeeAnalyticsMetric]:
    return await service.get_employee_analytics(
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/employees/{employee_id}",
    response_model=EmployeeAnalyticsMetric,
    status_code=status.HTTP_200_OK,
    summary="Get analytics for specific employee",
)
async def get_single_employee_analytics(
    employee_id: str,
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> EmployeeAnalyticsMetric:
    results = await service.get_employee_analytics(
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed attendance metrics found for employee '{employee_id}'.",
        )
    return results[0]


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Organization-wide attendance analytics summary",
    description="Aggregates overall organization attendance metrics alongside the breakdown for all active employees.",
)
async def get_organization_summary(
    start_date: Optional[datetime] = Query(None, description="Start date filter (UTC)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (UTC)"),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsSummaryResponse:
    return await service.get_organization_summary(
        start_date=start_date,
        end_date=end_date,
    )
