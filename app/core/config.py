from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "HROne Employee Attendance & Analytics API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # MongoDB Configuration
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "hrone_attendance"
    ATTENDANCE_COLLECTION: str = "attendance_records"
    AUDIT_COLLECTION: str = "attendance_audits"

    # Business Rules
    MAX_REASON_LENGTH: int = 500
    AUTO_ROUND_HOURS: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
