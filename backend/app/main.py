import sys
from pathlib import Path

# 将 app 目录加入 sys.path，使顶层模块（state/llm/agents/orchestrator）可被导入
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as api_router
from .api.websocket import websocket_endpoint

app = FastAPI(
    title="AdaptAI — Novel-to-Screenplay AI",
    description="将小说文本通过 AI 转换为结构化 YAML 剧本",
    version="0.2.0",
)

# ── CORS ──────────────────────────────────────────────────
# 前后端分离：允许前端从任意地址访问后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 开发阶段允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST API ──────────────────────────────────────────────
app.include_router(api_router)

# ── WebSocket ─────────────────────────────────────────────
@app.websocket("/ws/{thread_id}")
async def ws_endpoint(websocket: WebSocket, thread_id: str):
    await websocket_endpoint(websocket, thread_id)


@app.get("/")
async def root():
    """根路径 — 前端独立部署时返回 API 信息"""
    return {
        "service": "AdaptAI API",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "ok", "version": app.version}
