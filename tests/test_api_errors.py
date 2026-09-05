from fastapi.testclient import TestClient

from gecko_hide.api import DESIGN_INVALID, create_app


def test_invalid_export_design_returns_stable_failure_code():
    client = TestClient(create_app())
    response = client.post("/api/design/export", json={"version": 3})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == DESIGN_INVALID
    assert response.json()["detail"]["message"]
