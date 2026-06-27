from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints


class PredictionInput(BaseModel):
    """
    Validation of the request body.

    The body should be valid JSON with a text field
    for the model to predict on.

    Input example:
        {
            "text": "this is a text example"
        }
    """

    text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
        Field(..., description="Input text for model prediction"),
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"text": "this is a text example"},
            ]
        }
    }


class PredictionOutput(BaseModel):
    """
    Validation of the response body.

    The body should be valid JSON with two fields:
        - language_code: the code of the predicted language
        - confidence: probability associated with that prediction

    Output example:
        {
            "language_code": "IT",
            "confidence": 0.98
        }
    """

    language_code: Annotated[
        str, Field(..., description="Predicted language code", examples=["IT"])
    ]
    confidence: Annotated[
        float,
        Field(
            ..., ge=0.0, le=1.0, description="Prediction confidence score (0.0 to 1.0)"
        ),
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "language_code": "IT",
                    "confidence": 0.98,
                },
            ]
        }
    }
