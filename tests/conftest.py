import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.app import create_app
from src.api.dependencies import get_db
from src.db.base import Base

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    """Створює окремий in-memory SQLite для кожного тесту."""
    _engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest.fixture
async def db_session(engine):
    """Надає AsyncSession прив'язану до тестового движка."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def app_with_db(db_session: AsyncSession):
    """FastAPI-застосунок із підміненою залежністю БД."""
    application = create_app()

    async def _override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest.fixture
async def client(app_with_db):
    """Асинхронний HTTP-клієнт для тестових запитів."""
    async with AsyncClient(transport=ASGITransport(app=app_with_db), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_payload() -> list[dict]:
    """Один валідний ProcessedAgentData для POST-запитів."""
    return [
        {
            "road_state": "good",
            "agent_data": {
                "accelerometer": {"x": 1.0, "y": 0.5, "z": 9.8},
                "gps": {"latitude": 50.45, "longitude": 30.52},
                "time": "2026-03-19T10:00:00Z",
            },
        }
    ]
