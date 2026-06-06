# AI 小说转剧本工具

将 3 章以上的小说文本通过 AI 自动转换为结构化 YAML 剧本，全流程嵌入 HITL 人机协同编辑。

## 技术栈

- **后端**: Python FastAPI + asyncio + WebSocket
- **前端**: 原生 HTML/JS + htmx + Alpine.js
- **状态持久化**: SQLite (Repository 接口可迁移)
- **LLM**: 模型无关 Adapter 抽象层 (Claude / DeepSeek)

## 快速启动

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # 编辑 .env 填入 API Key
uvicorn app.main:app --reload --port 8000
```

访问 `http://localhost:8000`

## 项目结构

```
novel-to-screenplay/
├── backend/           # FastAPI 后端
│   ├── app/           # 应用代码
│   │   ├── api/       # REST + WebSocket
│   │   ├── agents/    # AI Agent + 规则引擎
│   │   ├── llm/       # LLM Adapter 抽象层
│   │   ├── state/     # State Store 持久化
│   │   ├── schemas/   # Pydantic 数据模型
│   │   └── orchestrator/ # Pipeline + 图引擎
│   └── tests/         # 测试
├── frontend/          # 前端静态文件
└── docs/              # 文档
```

## 设计文档

- [设计规格书](docs/superpowers/specs/2026-06-05-novel-to-screenplay-design.md)
- [YAML Schema 定义](docs/superpowers/specs/2026-06-05-screenplay-yaml-schema.md)
- [实现计划](docs/superpowers/plans/2026-06-05-novel-to-screenplay-plan.md)
