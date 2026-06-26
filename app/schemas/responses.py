from pydantic import BaseModel

""" 
Success Response was not defined since it corresponds to 
PredictionOuptut, defined in .language
"""


class ErrorResponse(BaseModel):
    """
    {
      "error_code": "validation_error",
      "message": "text field cannot be empty",
      "doc_url": "https://github.com/frapaparatto/py-langid-api#errors"
    }

    """

    # I need to add Annotated[] and so on
    error_code: str
    message: str
    doc_url: str
