"""API 集成测试 — REST 端点功能验证"""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── 健康检查 ──

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── 会话创建 ──

@pytest.mark.asyncio
async def test_create_session_with_text(client):
    response = await client.post("/api/sessions", data={"text": "## 第一章\n测试内容。"})
    assert response.status_code == 200
    data = response.json()
    assert "thread_id" in data
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_create_session_empty_text_fails(client):
    response = await client.post("/api/sessions", data={"text": ""})
    assert response.status_code == 400


# ── 会话查询 ──

@pytest.mark.asyncio
async def test_get_session(client):
    create_resp = await client.post("/api/sessions", data={"text": "## 第一章\n测试。"})
    thread_id = create_resp.json()["thread_id"]

    response = await client.get(f"/api/sessions/{thread_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"] == thread_id
    assert "artifacts" in data
    assert "pipeline_state" in data


@pytest.mark.asyncio
async def test_get_nonexistent_session(client):
    response = await client.get("/api/sessions/nonexistent-id")
    assert response.status_code == 404


# ── 会话列表 ──

@pytest.mark.asyncio
async def test_list_sessions(client):
    for _ in range(3):
        await client.post("/api/sessions", data={"text": "## 第一章\n测试。"})
    response = await client.get("/api/sessions")
    assert response.status_code == 200
    assert len(response.json()) >= 3


# ── 导出 ──

@pytest.mark.asyncio
async def test_export_without_script_fails(client):
    create_resp = await client.post("/api/sessions", data={"text": "## 第一章\n测试。"})
    thread_id = create_resp.json()["thread_id"]
    response = await client.get(f"/api/sessions/{thread_id}/export")
    assert response.status_code == 400
