def test_prediction_success(client):
    """Valid text with a real model: 200, exact success schema keys,
    non-empty language_code, confidence a float in [0.0, 1.0]."""
    response = client.post(
        "/identify-language",
        json={"text": "This is a sentence in English."},
    )
    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {"language_code", "confidence"}
    assert isinstance(body["language_code"], str)
    assert body["language_code"] != ""
    assert isinstance(body["confidence"], float)
    assert 0.0 <= body["confidence"] <= 1.0


def test_prediction_empty_string(client):
    """Empty text: 422 before the model is touched, ErrorResponse shape,
    error_code validation_error."""
    response = client.post(
        "/identify-language",
        json={"text": ""},
    )
    assert response.status_code == 422

    body = response.json()
    assert set(body.keys()) == {"error_code", "message", "doc_url"}
    assert body["error_code"] == "validation_error"


def test_prediction_whitespace_only(client):
    """Whitespace-only text: 422, ErrorResponse shape, error_code
    validation_error."""
    response = client.post(
        "/identify-language",
        json={"text": "   "},
    )
    assert response.status_code == 422

    body = response.json()
    assert set(body.keys()) == {"error_code", "message", "doc_url"}
    assert body["error_code"] == "validation_error"


def test_prediction_model_unavailable(client, override_model_none):
    """Model unavailable: 503, ErrorResponse shape, error_code
    model_unavailable."""
    response = client.post(
        "/identify-language",
        json={"text": "This is a sentence in English."},
    )
    assert response.status_code == 503

    body = response.json()
    assert set(body.keys()) == {"error_code", "message", "doc_url"}
    assert body["error_code"] == "model_unavailable"


def test_prediction_failed(client, override_model_raises):
    """Model raises during prediction: 500, ErrorResponse shape,
    error_code prediction_failed."""
    response = client.post(
        "/identify-language",
        json={"text": "This is a sentence in English."},
    )
    assert response.status_code == 500

    body = response.json()
    assert set(body.keys()) == {"error_code", "message", "doc_url"}
    assert body["error_code"] == "prediction_failed"
