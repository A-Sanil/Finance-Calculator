from fastapi.testclient import TestClient

from quant_agent.api.main import app

client = TestClient(app)


def test_recommendation_markdown_endpoint() -> None:
    response = client.post(
        "/recommendations/markdown",
        json={"tickers": ["AAPL"], "sec_ciks": {}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "markdown" in payload
    assert "AAPL" in payload["markdown"]
