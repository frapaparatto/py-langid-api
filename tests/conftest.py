import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_model


@pytest.fixture(scope="session")
def client():
    """
    TestClient wrapping the real app.

    Runs the app's real lifespan once for the whole test session, so
    app.state.model holds the actual unpickled model, not a stand-in.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def override_model_none():
    """
    Fake get_model to return None, simulating an unavailable model.

    Clears the override after the test so it does not leak into others.
    """
    app.dependency_overrides[get_model] = lambda: None
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_model_raises():
    """
    Fake get_model to return a model whose predict raises ValueError,
    simulating an unexpected prediction failure.

    Clears the override after the test so it does not leak into others.
    """

    class FailingModel:
        def predict(self, texts):
            raise ValueError("prediction failed")

    app.dependency_overrides[get_model] = lambda: FailingModel()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def restore_model_state():
    """
    Save app.state.model before the test and restore it after.

    The client fixture is session-scoped, so app.state.model persists
    across tests. Tests that mutate it directly need this fixture to
    avoid leaking that mutation into later tests.
    """
    original_model = app.state.model
    yield
    app.state.model = original_model
