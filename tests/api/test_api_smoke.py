import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_openapi_document_available():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]


@pytest.mark.asyncio
async def test_health_endpoint_responds_without_startup_dependencies():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code in (200, 503)
    assert response.json()["status"] in ("ok", "degraded")
