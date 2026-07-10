def test_not_found_unified_shape(client):
    """Unknown path: 404, unified ErrorResponse shape, error_code not_found."""
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 404

    body = response.json()
    assert set(body.keys()) == {"error_code", "message", "doc_url"}
    assert body["error_code"] == "not_found"
