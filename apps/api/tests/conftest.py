from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nodesh_api.database import Base, get_session
from nodesh_api.main import app
from nodesh_api.models.concept import Concept, DocumentConcept  # noqa: F401
from nodesh_api.models.document import Document  # noqa: F401
from nodesh_api.models.relationship import ConceptRelationship, RelationshipEvidence  # noqa: F401
from nodesh_api.models.workspace import Workspace  # noqa: F401
from nodesh_api.storage import get_uploads_directory


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_get_session() -> Generator[Session, None, None]:
        session = test_session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_uploads_directory] = lambda: tmp_path / "uploads"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
