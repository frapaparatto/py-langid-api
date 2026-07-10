from typing import Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Validation of the health check response body.

    Always status "OK": a successful response means the health check
    itself ran, which is the endpoint's only responsibility. model_loaded
    reports the model's real readiness state as data, not as the HTTP
    status code.

    Output example:
        {
            "status": "OK",
            "model_loaded": true
        }
    """

    status: Literal["OK"] = Field(
        ..., description="Liveness indicator, always OK for a successful response"
    )
    model_loaded: bool = Field(
        ..., description="Whether the model was loaded at startup"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"status": "OK", "model_loaded": True},
            ]
        }
    }
