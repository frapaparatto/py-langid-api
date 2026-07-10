from typing import Any
from ..schemas.language import PredictionInput, PredictionOutput
from ..core.exceptions import ModelUnavailableError, PredictionFailedError


def predict(input: PredictionInput, model: Any):
    """
    Predict the language of the input text and its confidence score.

    Raises ModelUnavailableError if model is None, meaning it was not
    loaded at startup. Raises PredictionFailedError, chaining the
    original exception as its cause, if predict or predict_proba raises
    for any other reason.

    Confidence is the highest class probability from predict_proba,
    rounded to 3 decimal places, not necessarily the same computation
    predict itself uses internally to choose the label.

    Returns a PredictionOutput with the predicted language_code and the
    confidence score.
    """
    if model is None:
        raise ModelUnavailableError()

    try:
        language_code = model.predict([input.text])[0]
        confidence = round(model.predict_proba([input.text])[0].max(), 3)
    except Exception as e:
        raise PredictionFailedError() from e

    return PredictionOutput(language_code=language_code, confidence=confidence)
