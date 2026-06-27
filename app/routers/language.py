from fastapi import APIRouter, Depends
from typing import Any
from ..schemas.language import PredictionInput, PredictionOutput
from ..core.dependencies import get_model
from ..service.model import predict
from ..schemas.responses import ErrorResponse


router = APIRouter()


@router.post(
    "/identify-language",
    response_model=PredictionOutput,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        503: {"model": ErrorResponse, "description": "Model unavailable"},
        500: {"model": ErrorResponse, "description": "Prediction failed"},
    },
)
def identify_language(input: PredictionInput, model: Any = Depends(get_model)) -> Any:
    """
    Identify the language of a text.

    Takes a text field and returns the predicted language code and a
    confidence score between 0 and 1. The supported languages are the ones
    the model was trained on (EN, DE, IT); text in any other language is
    classified as the closest of these.

    Confidence is reported as data, not judged: a low score is still a
    successful response, and the caller decides what threshold is
    acceptable for its own use.

    The model is injected via a dependency that reads it from app.state.
    The route stays thin: validation and injection happen before it runs,
    and prediction errors are raised by the service and translated to the
    documented error responses by the registered handlers.
    """
    return predict(input, model)
