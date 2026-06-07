"""AdaptAI FastAPI 应用入口"""

import sys
from pathlib import Path

# 将 app 目录加入 sys.path，使顶层模块（state/llm/agents/orchestrator）可被导入
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from .api.routes import router as api_router
from .api.websocket import websocket_endpoint

app = FastAPI(
    title="AdaptAI — Novel-to-Screenplay AI",
    description="将小说文本通过 AI 转换为结构化 YAML 剧本",
    version="0.2.0",
)

# ── CORS ──────────────────────────────────────────────────
# 前后端分离：开发阶段允许 localhost:5500/live-server 等来源
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "null",  # 直接打开 HTML 文件时的 origin
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ──────────────────────────────────────────
# 简单的滑动窗口限流器：每个 IP 每分钟最多 30 次请求
import asyncio
_rate_records: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW = 60.0   # 窗口：60 秒
_RATE_LIMIT_MAX = 30        # 最大请求数


async def _cleanup_stale_ips():
    """定期清理超过窗口期的 IP 记录，防止内存泄漏"""
    while True:
        await asyncio.sleep(300)  # 每 5 分钟清理一次
        now = time.time()
        stale_ips = [
            ip for ip, records in _rate_records.items()
            if not records or all(now - t > _RATE_LIMIT_WINDOW for t in records)
        ]
        for ip in stale_ips:
            _rate_records.pop(ip, None)


@app.on_event("startup")
async def startup():
    asyncio.create_task(_cleanup_stale_ips())


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    if client_ip not in _rate_records:
        _rate_records[client_ip] = []

    # 清理过期记录
    _rate_records[client_ip] = [
        t for t in _rate_records[client_ip] if now - t < _RATE_LIMIT_WINDOW
    ]

    if len(_rate_records[client_ip]) >= _RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"},
        )

    _rate_records[client_ip].append(now)
    return await call_next(request)

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
