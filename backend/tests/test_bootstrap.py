"""First-admin bootstrap: the CLI command, the startup hook and the production secret check."""

import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.main as main_module
from app.cli import create_admin
from app.core.config import Settings
from app.core.security import verify_password
from app.models.user import User, UserRole


async def _users(session: AsyncSession, email: str) -> list[User]:
    session.expire_all()
    return list((await session.scalars(select(User).where(User.email == email))).all())


async def test_cli_create_admin_is_idempotent(session_factory, session, capsys) -> None:
    assert await create_admin("Boss@Example.com", "Admin12345", session_factory) == 0
    assert "Created admin boss@example.com" in capsys.readouterr().out

    assert await create_admin("boss@example.com", "Other12345", session_factory) == 0
    assert "already exists" in capsys.readouterr().out

    users = await _users(session, "boss@example.com")
    assert len(users) == 1
    assert users[0].role == UserRole.admin
    # running it again does not overwrite the existing password
    assert verify_password("Admin12345", users[0].hashed_password)


async def test_cli_promotes_existing_user(session_factory, session, make_user) -> None:
    await make_user("promote-me@example.com", role=UserRole.trader, is_active=False)
    assert await create_admin("promote-me@example.com", "Admin12345", session_factory) == 0
    [user] = await _users(session, "promote-me@example.com")
    assert user.role == UserRole.admin
    assert user.is_active is True


async def test_cli_rejects_invalid_input(session_factory, session, capsys) -> None:
    assert await create_admin("bad@example.com", "weak", session_factory) == 2
    assert await create_admin("not-an-email", "Admin12345", session_factory) == 2
    assert "Invalid input" in capsys.readouterr().err
    assert await _users(session, "bad@example.com") == []


@pytest.fixture
def bootstrap_env(monkeypatch, session_factory):
    monkeypatch.setattr(main_module, "SessionLocal", session_factory)
    monkeypatch.setattr(main_module.settings, "first_admin_email", "first@example.com")
    monkeypatch.setattr(main_module.settings, "first_admin_password", "First12345")


async def test_startup_creates_first_admin(bootstrap_env, session) -> None:
    await main_module.bootstrap_first_admin()
    [user] = await _users(session, "first@example.com")
    assert user.role == UserRole.admin
    # second start-up does nothing
    await main_module.bootstrap_first_admin()
    assert len(await _users(session, "first@example.com")) == 1


async def test_startup_skips_when_an_admin_exists(bootstrap_env, session, make_user) -> None:
    await make_user("existing-admin@example.com", role=UserRole.admin)
    await main_module.bootstrap_first_admin()
    assert await _users(session, "first@example.com") == []
    total = await session.scalar(select(func.count()).select_from(User))
    assert total == 1


async def test_startup_skips_when_not_configured(monkeypatch, session_factory, session) -> None:
    monkeypatch.setattr(main_module, "SessionLocal", session_factory)
    monkeypatch.setattr(main_module.settings, "first_admin_email", "")
    monkeypatch.setattr(main_module.settings, "first_admin_password", "")
    await main_module.bootstrap_first_admin()
    assert await session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize("secret", ["change-me", "short-secret", "x" * 31])
def test_production_rejects_weak_jwt_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET is insecure"):
        Settings(_env_file=None, environment="production", jwt_secret=secret)


def test_production_accepts_strong_jwt_secret() -> None:
    Settings(_env_file=None, environment="production", jwt_secret="x" * 32)
    Settings(_env_file=None, environment="development", jwt_secret="change-me")


async def test_concurrent_startups_create_one_admin(monkeypatch, migrated_db) -> None:
    """uvicorn --workers 2: every process runs the bootstrap at once on its own connection."""
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(main_module, "SessionLocal", factory)
    monkeypatch.setattr(main_module.settings, "first_admin_email", "race@example.com")
    monkeypatch.setattr(main_module.settings, "first_admin_password", "First12345")
    try:
        await asyncio.gather(*(main_module.bootstrap_first_admin() for _ in range(4)))
        async with factory() as s:
            assert len(await _users(s, "race@example.com")) == 1
    finally:
        async with factory() as s:
            await s.execute(delete(User).where(User.email == "race@example.com"))
            await s.commit()
        await engine.dispose()
