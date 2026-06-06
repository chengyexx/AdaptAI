from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(
    title="Novel-to-Screenplay AI Tool",
    description="将小说文本通过 AI 转换为结构化 YAML 剧本",
    version="0.1.0",
)

# 挂载前端静态文件
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "ok", "version": app.version}
