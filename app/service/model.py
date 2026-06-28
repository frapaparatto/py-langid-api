from typing import Any
from ..schemas.language import PredictionInput, PredictionOutput
from ..core.exceptions import ModelUnavailableError, PredictionFailedError


def predict(input: PredictionInput, model: Any):
    if model is None:
        raise ModelUnavailableError()

    try:
        language_code = model.predict([input.text])[0]
        confidence = round(model.predict_proba([input.text])[0].max(), 3)
    except Exception as e:
        raise PredictionFailedError() from e

    return PredictionOutput(language_code=language_code, confidence=confidence)
