import pytest
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app


@pytest.fixture
def mock_mongo_client() -> AsyncMongoMockClient:
    return AsyncMongoMockClient()


@pytest.fixture
def mock_db(mock_mongo_client: AsyncMongoMockClient):
    return mock_mongo_client[settings.DATABASE_NAME]


@pytest.fixture(autouse=True)
def override_database_dependency(mock_db):
    """Overrides the FastAPI get_db dependency for test isolation."""
    async def _get_test_db():
        return mock_db

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an asynchronous HTTP test client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
