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

# ── 端到端集成测试 ──

@pytest.mark.asyncio
async def test_full_session_lifecycle(client):
    """完整生命周期：创建→查询→列表→导出前状态"""
    resp = await client.post("/api/sessions", data={"text": "## 第一章\n测试。\n## 第二章\n更多。\n## 第三章\n结尾。"})
    assert resp.status_code == 200
    tid = resp.json()["thread_id"]

    resp = await client.get(f"/api/sessions/{tid}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"

    resp = await client.get("/api/sessions")
    assert any(s["thread_id"] == tid for s in resp.json())

    resp = await client.get(f"/api/sessions/{tid}/export")
    assert resp.status_code == 400  # 未生成


@pytest.mark.asyncio
async def test_hitl_submit_updates_state(client):
    """HITL 提交：创建→提交角色编辑→状态更新"""
    resp = await client.post("/api/sessions", data={"text": "## 第一章\n林墨。\n## 第二章\n小禾。\n## 第三章\n对话。"})
    tid = resp.json()["thread_id"]
    edits = {"characters": [{"id": "c1", "name": "林墨", "aliases": [], "description": {"role": "protagonist"}, "relationships": []}]}
    resp = await client.post(f"/api/sessions/{tid}/hitl/continue", json=edits)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_sessions_unique_ids():
    """并发创建——thread_id 全部唯一"""
    import asyncio
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    transport = ASGITransport(app=app)
    async def create():
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.post("/api/sessions", data={"text": "## 第一章\n测试。"})
    results = await asyncio.gather(*[create() for _ in range(5)])
    tids = {r.json()["thread_id"] for r in results}
    assert len(tids) == 5


@pytest.mark.asyncio
async def test_all_endpoints_404_on_missing():
    """不存在的会话——所有GET端点返回404"""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for path in ["/api/sessions/fake-id", "/api/sessions/fake-id/export"]:
            resp = await ac.get(path)
            assert resp.status_code == 404, f"{path}"


@pytest.mark.asyncio
async def test_empty_text_variants_rejected():
    """空文本/空白/换行——全部返回400"""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for text in ["", "   ", "\n\n"]:
            resp = await ac.post("/api/sessions", data={"text": text})
            assert resp.status_code == 400, f"text={repr(text)}"
