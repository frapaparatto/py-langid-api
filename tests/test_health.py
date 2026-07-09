def test_health_model_present(client, restore_model_state):
    """Model set: health reports model_loaded true, status 200."""
    client.app.state.model = object()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is True


def test_health_model_absent(client, restore_model_state):
    """Model absent: health reports model_loaded false, status 200."""
    client.app.state.model = None
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is False
