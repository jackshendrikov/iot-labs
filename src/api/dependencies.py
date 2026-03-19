from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import get_db_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Надає сесію бази даних для ін'єкції у маршрути."""
    async for session in get_db_session():
        yield session
