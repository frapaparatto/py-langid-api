from fastapi import Request


def get_model(request: Request):
    """Returns the pre-loaded machine learning model"""
    return request.app.state.model
