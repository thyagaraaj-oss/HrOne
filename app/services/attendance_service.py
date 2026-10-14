from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.exceptions import (
    ActivePunchNotFoundException,
    AttendanceRecordNotFoundException,
    DuplicateActivePunchException,
    InvalidCorrectionException,
    InvalidPunchTimestampException,
)
from app.models.attendance import (
    AttendanceCorrectionRequest,
    AttendanceResponse,
    PunchInRequest,
    PunchOutRequest,
    PunchStatus,
)
from app.models.audit import AuditTrailResponse


def _serialize_id(val: Any) -> str:
    return str(val) if isinstance(val, ObjectId) else str(val)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_attendance_response(doc: Dict[str, Any]) -> AttendanceResponse:
    return AttendanceResponse(
        id=_serialize_id(doc["_id"]),
        employee_id=doc["employee_id"],
        punch_in=doc["punch_in"],
        punch_out=doc.get("punch_out"),
        working_hours=doc.get("working_hours"),
        status=PunchStatus(doc.get("status", PunchStatus.ACTIVE.value)),
        is_corrected=doc.get("is_corrected", False),
        correction_count=doc.get("correction_count", 0),
        location=doc.get("location"),
        notes=doc.get("notes"),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
    )


def _to_audit_response(doc: Dict[str, Any]) -> AuditTrailResponse:
    # Serialize datetimes or ObjectIds inside state dictionaries for clean JSON output
    def _sanitize(val: Any) -> Any:
        if isinstance(val, (datetime, ObjectId)):
            return str(val)
        if isinstance(val, dict):
            return {k: _sanitize(v) for k, v in val.items()}
        if isinstance(val, list):
            return [_sanitize(x) for x in val]
        return val

    return AuditTrailResponse(
        id=_serialize_id(doc["_id"]),
        attendance_id=str(doc["attendance_id"]),
        employee_id=str(doc["employee_id"]),
        changed_by=doc["changed_by"],
        reason=doc["reason"],
        previous_state=_sanitize(doc.get("previous_state", {})),
        new_state=_sanitize(doc.get("new_state", {})),
        timestamp=doc["timestamp"],
    )


class AttendanceService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[settings.ATTENDANCE_COLLECTION]
        self.audit_collection = db[settings.AUDIT_COLLECTION]

    async def punch_in(self, payload: PunchInRequest) -> AttendanceResponse:
        now = datetime.now(timezone.utc)
        punch_in_time = _to_utc(payload.timestamp) or now

        # Business Rule 1: Check for active punches without punch_out
        existing_active = await self.collection.find_one(
            {"employee_id": payload.employee_id, "punch_out": None}
        )
        if existing_active:
            raise DuplicateActivePunchException(
                employee_id=payload.employee_id,
                active_record_id=_serialize_id(existing_active["_id"]),
            )

        doc = {
            "employee_id": payload.employee_id,
            "punch_in": punch_in_time,
            "punch_out": None,
            "working_hours": None,
            "status": PunchStatus.ACTIVE.value,
            "is_corrected": False,
            "correction_count": 0,
            "location": payload.location,
            "notes": payload.notes,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await self.collection.insert_one(doc)
            doc["_id"] = result.inserted_id
            return _to_attendance_response(doc)
        except DuplicateKeyError:
            # Handles concurrency race condition where two requests punch in at the same moment
            raise DuplicateActivePunchException(employee_id=payload.employee_id)

    async def punch_out(self, payload: PunchOutRequest) -> AttendanceResponse:
        now = datetime.now(timezone.utc)
        punch_out_time = _to_utc(payload.timestamp) or now

        # Business Rule 2: Ensure an active punch session exists
        active_record = await self.collection.find_one(
            {"employee_id": payload.employee_id, "punch_out": None}
        )
        if not active_record:
            raise ActivePunchNotFoundException(employee_id=payload.employee_id)

        punch_in_time = _to_utc(active_record["punch_in"])
        if punch_in_time and punch_out_time < punch_in_time:
            raise InvalidPunchTimestampException(
                f"Punch-out time ({punch_out_time.isoformat()}) cannot be earlier than punch-in time ({punch_in_time.isoformat()})."
            )

        duration_seconds = (punch_out_time - punch_in_time).total_seconds()
        working_hours = round(duration_seconds / 3600.0, 2)

        update_fields: Dict[str, Any] = {
            "punch_out": punch_out_time,
            "working_hours": working_hours,
            "status": PunchStatus.COMPLETED.value,
            "updated_at": now,
        }

        if payload.notes:
            existing_notes = active_record.get("notes")
            update_fields["notes"] = (
                f"{existing_notes} | {payload.notes}" if existing_notes else payload.notes
            )

        await self.collection.update_one(
            {"_id": active_record["_id"]},
            {"$set": update_fields},
        )

        updated_doc = await self.collection.find_one({"_id": active_record["_id"]})
        return _to_attendance_response(updated_doc)

    async def correct_attendance(
        self, record_id: str, payload: AttendanceCorrectionRequest
    ) -> Dict[str, Any]:
        target_id: Any = record_id
        try:
            target_id = ObjectId(record_id)
        except (InvalidId, TypeError):
            pass

        record = await self.collection.find_one({"_id": target_id})
        if not record and isinstance(target_id, ObjectId):
            record = await self.collection.find_one({"_id": str(target_id)})
        elif not record and isinstance(target_id, str):
            try:
                record = await self.collection.find_one({"_id": ObjectId(target_id)})
            except (InvalidId, TypeError):
                pass

        if not record:
            raise AttendanceRecordNotFoundException(record_id=record_id)

        now = datetime.now(timezone.utc)
        existing_punch_in = _to_utc(record["punch_in"])
        existing_punch_out = _to_utc(record.get("punch_out"))

        new_punch_in = _to_utc(payload.punch_in) if payload.punch_in else existing_punch_in
        new_punch_out = (
            _to_utc(payload.punch_out) if payload.punch_out is not None else existing_punch_out
        )

        # Validation: punch_out must not precede punch_in
        if new_punch_in and new_punch_out and new_punch_out < new_punch_in:
            raise InvalidCorrectionException(
                f"Corrected punch-out ({new_punch_out.isoformat()}) cannot be before punch-in ({new_punch_in.isoformat()})."
            )

        # Recalculate working hours and status
        if new_punch_in and new_punch_out:
            duration_seconds = (new_punch_out - new_punch_in).total_seconds()
            new_working_hours = round(duration_seconds / 3600.0, 2)
            new_status = payload.status.value if payload.status else PunchStatus.COMPLETED.value
        else:
            new_working_hours = None
            new_status = payload.status.value if payload.status else PunchStatus.ACTIVE.value

        previous_state = {
            "punch_in": existing_punch_in.isoformat() if existing_punch_in else None,
            "punch_out": existing_punch_out.isoformat() if existing_punch_out else None,
            "working_hours": record.get("working_hours"),
            "status": record.get("status"),
        }

        new_state = {
            "punch_in": new_punch_in.isoformat() if new_punch_in else None,
            "punch_out": new_punch_out.isoformat() if new_punch_out else None,
            "working_hours": new_working_hours,
            "status": new_status,
        }

        # 1. Insert Immutable Audit Log
        audit_doc = {
            "attendance_id": str(record["_id"]),
            "employee_id": record["employee_id"],
            "changed_by": payload.changed_by,
            "reason": payload.reason,
            "previous_state": previous_state,
            "new_state": new_state,
            "timestamp": now,
        }
        audit_res = await self.audit_collection.insert_one(audit_doc)
        audit_doc["_id"] = audit_res.inserted_id

        # 2. Update Attendance Record
        update_dict: Dict[str, Any] = {
            "punch_in": new_punch_in,
            "punch_out": new_punch_out,
            "working_hours": new_working_hours,
            "status": new_status,
            "is_corrected": True,
            "updated_at": now,
        }

        await self.collection.update_one(
            {"_id": record["_id"]},
            {
                "$set": update_dict,
                "$inc": {"correction_count": 1},
            },
        )

        updated_record = await self.collection.find_one({"_id": record["_id"]})
        return {
            "attendance": _to_attendance_response(updated_record),
            "audit_trail": _to_audit_response(audit_doc),
        }

    async def get_by_id(self, record_id: str) -> AttendanceResponse:
        target_id: Any = record_id
        try:
            target_id = ObjectId(record_id)
        except (InvalidId, TypeError):
            pass

        doc = await self.collection.find_one({"_id": target_id})
        if not doc and isinstance(target_id, ObjectId):
            doc = await self.collection.find_one({"_id": str(target_id)})
        elif not doc and isinstance(target_id, str):
            try:
                doc = await self.collection.find_one({"_id": ObjectId(target_id)})
            except (InvalidId, TypeError):
                pass

        if not doc:
            raise AttendanceRecordNotFoundException(record_id=record_id)
        return _to_attendance_response(doc)

    async def list_records(
        self,
        employee_id: Optional[str] = None,
        status: Optional[PunchStatus] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[AttendanceResponse]:
        query: Dict[str, Any] = {}
        if employee_id:
            query["employee_id"] = employee_id
        if status:
            query["status"] = status.value

        cursor = self.collection.find(query).sort("punch_in", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_to_attendance_response(doc) for doc in docs]

    async def get_audit_trail(
        self,
        attendance_id: Optional[str] = None,
        employee_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditTrailResponse]:
        query: Dict[str, Any] = {}
        if attendance_id:
            query["attendance_id"] = attendance_id
        if employee_id:
            query["employee_id"] = employee_id

        cursor = self.audit_collection.find(query).sort("timestamp", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_to_audit_response(doc) for doc in docs]
