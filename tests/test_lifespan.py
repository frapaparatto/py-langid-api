from fastapi.testclient import TestClient

from app.main import create_app, routers, exception_handlers
from app.core.config import settings


def test_lifespan_loads_model_when_file_present(monkeypatch):
    """Startup with a valid model path: app.state.model is loaded (not None)."""
    monkeypatch.setattr(settings, "model_path", "./model.pkl")
    app = create_app(routers, exception_handlers)
    with TestClient(app):
        assert app.state.model is not None


def test_lifespan_leaves_model_none_when_file_absent(monkeypatch, tmp_path):
    """Startup with a missing model path: app.state.model stays None."""
    missing = tmp_path / "does_not_exist.pkl"
    monkeypatch.setattr(settings, "model_path", str(missing))
    app = create_app(routers, exception_handlers)
    with TestClient(app):
        assert app.state.model is None
