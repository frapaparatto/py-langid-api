from typing import Any
from ..schemas.language import PredictionInput, PredictionOutput
from ..core.exceptions import ModelUnavailableError, PredictionFailedError


def predict(input: PredictionInput, model: Any):
    if model is None:
        raise ModelUnavailableError()

    language_code = model.predict([input.text])[0]
    confidence = model.predict_proba([input.text])[0].max()

    if language_code is None or confidence is None:
        raise PredictionFailedError()

    return PredictionOutput(language_code=language_code, confidence=confidence)
