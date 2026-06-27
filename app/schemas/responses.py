from typing import Annotated
from pydantic import BaseModel, Field

"""
Success response corresponds to PredictionOutput defined in .language.
"""


class ErrorResponse(BaseModel):
    """
    Validation of the error response body.

    The body should be valid JSON with three fields:
        - error_code: a machine-readable error identifier
        - message: a human-readable description of the error
        - doc_url: a link to relevant documentation

    Output example:
        {
            "error_code": "validation_error",
            "message": "text field cannot be empty",
            "doc_url": "https://github.com/frapaparatto/py-langid-api#errors"
        }
    """

    error_code: Annotated[
        str,
        Field(
            ...,
            description="Machine-readable error identifier",
            examples=["validation_error"],
        ),
    ]
    message: Annotated[
        str,
        Field(
            ...,
            description="Human-readable description of the error",
            examples=["text field cannot be empty"],
        ),
    ]
    doc_url: Annotated[
        str,
        Field(
            ...,
            description="URL pointing to relevant error documentation",
            examples=["https://github.com/frapaparatto/py-langid-api#errors"],
        ),
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error_code": "validation_error",
                    "message": "text field cannot be empty",
                    "doc_url": "https://github.com/frapaparatto/py-langid-api#errors",
                }
            ]
        }
    }
