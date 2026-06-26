from fastapi import APIRouter, Depends
from typing import Any
from ..schemas.language import PredictionInput, PredictionOutput
from ..core.dependencies import get_model
from ..service.model import predict


router = APIRouter()


@router.post("/identify-language", response_model=PredictionOutput)
def identify_language(input: PredictionInput, model: Any = Depends(get_model)) -> Any:
    return predict(input, model)
