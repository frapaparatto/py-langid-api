from fastapi import APIRouter, Request

from ..schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    """
    Liveness and model-readiness check.

    Always returns 200: a successful response means the health check
    itself ran, which is the endpoint's only responsibility. The model's
    state is reported as data in the body, not as the status code.

    The model_loaded field reflects whether the model was loaded at
    startup. It is informational only: this endpoint reports the state but
    does not act on it. Acting on an unavailable model (returning 503) is
    the prediction route's responsibility, keeping the two concerns
    separate.

    The model is read directly from app.state via the request, rather than
    through the prediction dependency, so the check stays independent of
    the prediction path.
    """
    model_loaded = request.app.state.model is not None
    return HealthResponse(status="OK", model_loaded=model_loaded)
