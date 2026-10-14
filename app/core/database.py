import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("hrone.database")


class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect_to_database(cls, uri: Optional[str] = None, db_name: Optional[str] = None) -> None:
        mongo_uri = uri or settings.MONGODB_URL
        target_db = db_name or settings.DATABASE_NAME
        logger.info(f"Connecting to MongoDB at {mongo_uri} (db: {target_db})")

        cls.client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
        cls.db = cls.client[target_db]

        # Verify connectivity if server is reachable
        try:
            await cls.client.admin.command("ping")
            logger.info("MongoDB connection ping successful.")
            await cls.create_indexes()
        except Exception as e:
            logger.warning(f"Could not ping MongoDB or create indexes immediately: {e}")

    @classmethod
    async def create_indexes(cls) -> None:
        if cls.db is None:
            return

        attendance_col = cls.db[settings.ATTENDANCE_COLLECTION]
        audit_col = cls.db[settings.AUDIT_COLLECTION]

        try:
            # 1. Unique Partial Index: Guarantees at database-level that an employee
            # cannot have more than ONE active punch (punch_out: null) at any time.
            await attendance_col.create_index(
                [("employee_id", 1)],
                unique=True,
                partialFilterExpression={"punch_out": None},
                name="idx_unique_active_punch_per_employee",
            )

            # 2. Compound Index: Querying attendance by employee & date ordering
            await attendance_col.create_index(
                [("employee_id", 1), ("punch_in", -1)],
                name="idx_employee_punch_in_desc",
            )

            # 3. Analytics Index: Optimized for aggregation filtering
            await attendance_col.create_index(
                [("status", 1), ("punch_in", 1), ("employee_id", 1)],
                name="idx_status_punchin_employee",
            )

            # 4. Audit Indexes: Rapid lookups by attendance record and employee
            await audit_col.create_index(
                [("attendance_id", 1), ("timestamp", -1)],
                name="idx_audit_attendance_time",
            )
            await audit_col.create_index(
                [("employee_id", 1), ("timestamp", -1)],
                name="idx_audit_employee_time",
            )
            logger.info("MongoDB indexes verified/created successfully.")
        except Exception as e:
            logger.warning(f"Index creation encountered an error: {e}")

    @classmethod
    async def close_database_connection(cls) -> None:
        if cls.client is not None:
            logger.info("Closing MongoDB connection.")
            cls.client.close()
            cls.client = None
            cls.db = None

    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        if cls.db is None:
            raise RuntimeError("Database connection has not been initialized.")
        return cls.db


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI Dependency for obtaining the active Motor database instance."""
    return DatabaseManager.get_database()
