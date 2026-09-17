import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create any missing tables directly from the ORM metadata.

    Convenience path for fresh and throwaway databases. It creates missing
    *tables* only — it never alters an existing one — so schema changes to
    existing tables must go through Alembic. See `alembic/versions/`.
    """
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def bootstrap() -> None:
    """Bring a database up to a usable state on application startup."""
    if settings.auto_create_tables:
        await init_db()

    from app.db.seed import seed_rbac

    async with AsyncSessionLocal() as session:
        await seed_rbac(session)

    await warn_if_schema_behind()


async def warn_if_schema_behind() -> None:
    """Log loudly when the database is not at the latest Alembic revision.

    A stale schema produces confusing `UndefinedColumnError`s at runtime, so it
    is worth saying so explicitly. This never raises: refusing to boot would be
    hostile during development.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    try:
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()

        async with engine.connect() as conn:
            result = await conn.execute(text("select version_num from alembic_version"))
            current = result.scalar_one_or_none()
    except Exception:  # noqa: BLE001 - never block startup over a diagnostic
        logger.debug("could not determine alembic revision", exc_info=True)
        return

    if current != head:
        logger.error(
            "database schema is out of date (current=%s head=%s) — run `alembic upgrade head`",
            current,
            head,
        )
