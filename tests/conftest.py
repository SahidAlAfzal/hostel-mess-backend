import os
import pytest   # type: ignore
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base


DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(scope='session', autouse=True)
def create_test_schema():
    # Tables already exist because your CI runs `alembic upgrade head`
    # before pytest. This fixture just guarantees a clean slate if run locally.
    
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    


@pytest.fixture
def get_test_db():
    connection = engine.connect()
    transaction = connection.begin()
    
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
    
    

@pytest.fixture
def client(get_test_db):
    
    app.dependency_overrides[get_db] = lambda: get_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    
