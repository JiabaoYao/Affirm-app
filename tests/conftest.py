import os

# Before importing the app: env vars override .env, so tests never depend on local secrets.
os.environ["JWT_SECRET"] = "test-secret-that-is-at-least-32-bytes-long"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.decisioning import ensure_risk_tiers


@pytest.fixture()
def session_factory():
    """Fresh in-memory SQLite database per test (StaticPool keeps one shared connection)."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        ensure_risk_tiers(db)
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager, so the app's Postgres startup hook doesn't run.
    yield TestClient(app)
    app.dependency_overrides.clear()
