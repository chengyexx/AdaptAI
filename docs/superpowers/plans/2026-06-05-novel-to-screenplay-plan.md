# AI 小说转剧本工具 — 实现计划

> **致 agentic workers:** 必须使用子技能：推荐 superpowers:subagent-driven-development 来逐个任务实现此计划。步骤使用 `- [ ]` 复选框语法供追踪。

**目标:** 构建一个 Web 应用，将 3 章以上的小说文本通过 AI 转换为结构化 YAML 剧本，全流程嵌入 HITL 人机协同编辑能力。

**架构:** FastAPI 后端 + 原生 HTML/JS 前端（htmx + Alpine.js），Agent 驱动 Pipeline + 图引擎双模 Orchestrator，模型无关 LLM Adapter 抽象层，SQLite State Store 持久化。

**技术栈:** Python 3.11+, FastAPI, asyncio, SQLite, htmx, Alpine.js, jiter (Streaming JSON Parser)

**仓库:** 远程 Git 仓库已就绪（用户提供 URL），15 个 PR 递增交付

---

## 文件结构

```
novel-to-screenplay/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI 应用入口，挂载路由和 WebSocket
│   │   ├── config.py                   # 环境变量配置 (pydantic-settings)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py               # REST 端点 (sessions CRUD, HITL, export)
│   │   │   └── websocket.py            # WebSocket 连接管理 + 消息路由
│   │   ├── orchestrator/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py             # Happy Path 线性流水线
│   │   │   ├── graph_engine.py         # 图引擎 (HITL 分支, 重试循环, 条件边)
│   │   │   └── state_machine.py        # PipelineState 枚举 + 状态转换规则
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # BaseAgent 抽象类 + AgentResult
│   │   │   ├── chapter_parser.py       # 章节解析器 (规则引擎，非 AI)
│   │   │   ├── character_agent.py      # 角色识别 Agent
│   │   │   ├── scene_agent.py          # 场景切分 Agent
│   │   │   ├── script_agent.py         # 剧本生成 Agent
│   │   │   └── validator.py            # 校验器 (规则引擎，非 AI)
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py              # LLMAdapter 协议 (Protocol class)
│   │   │   ├── claude_adapter.py       # ClaudeAdapter (Anthropic SDK)
│   │   │   ├── deepseek_adapter.py     # DeepSeekAdapter (DeepSeek API)
│   │   │   ├── factory.py              # AdapterFactory + from_env()
│   │   │   └── streaming_parser.py     # StreamingJSONParser (jiter)
│   │   ├── state/
│   │   │   ├── __init__.py
│   │   │   ├── repository.py           # StateRepository 接口 (ABC)
│   │   │   ├── sqlite_store.py         # SQLite 实现 + Checkpointer
│   │   │   └── models.py               # SessionState, Artifacts, HITLRequest
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── screenplay.py           # Pydantic models (Screenplay, Scene, Character...)
│   │   └── prompts/                    # Prompt 模板 (独立 .txt 文件)
│   │       └── templates/
│   │           ├── character_agent/
│   │           │   └── v1/
│   │           │       ├── system.txt
│   │           │       └── user.txt
│   │           ├── scene_agent/
│   │           │   └── v1/
│   │           │       ├── system.txt
│   │           │       └── user.txt
│   │           └── script_agent/
│   │               └── v1/
│   │                   ├── system.txt
│   │                   └── user.txt
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # pytest fixtures (mock adapter, tmp db, sample novel)
│   │   ├── test_chapter_parser.py
│   │   ├── test_character_agent.py
│   │   ├── test_scene_agent.py
│   │   ├── test_script_agent.py
│   │   ├── test_validator.py
│   │   ├── test_pipeline.py
│   │   ├── test_graph_engine.py
│   │   ├── test_state_store.py
│   │   ├── test_adapters.py
│   │   ├── test_streaming_parser.py
│   │   └── test_api.py
│   ├── data/                           # State Store 数据目录 (gitignore)
│   │   └── .gitkeep
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html                      # 首页：上传/粘贴小说
│   ├── workspace.html                  # 工作台：Pipeline 进度 + HITL 编辑 + YAML 预览
│   ├── export.html                     # 导出页：下载/复制 YAML
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── state.js                    # StateProvider：session 状态管理
│       ├── websocket.js                # WebSocket 客户端 + 指数退避重连
│       ├── pipeline.js                 # Pipeline 进度条 + 阶段面板 UI
│       ├── hitl.js                     # HITL 编辑器组件 (角色卡/场景卡)
│       └── streaming.js                # Streaming JSON 增量渲染器
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   ├── 2026-06-05-novel-to-screenplay-design.md
│       │   └── 2026-06-05-screenplay-yaml-schema.md
│       └── plans/
│           └── 2026-06-05-novel-to-screenplay-plan.md
└── README.md
```

---

### Task 1: 项目脚手架 + Git 仓库初始化 (PR 1)

**分支:** `feat/project-setup`

**文件:**
- 创建: `backend/requirements.txt`
- 创建: `backend/.env.example`
- 创建: `backend/app/__init__.py`
- 创建: `backend/app/config.py`
- 创建: `backend/app/main.py`
- 创建: `backend/tests/__init__.py`
- 创建: `backend/tests/conftest.py`
- 创建: `backend/data/.gitkeep`
- 创建: `frontend/index.html` (占位)
- 创建: `.gitignore`
- 创建: `README.md`

- [ ] **Step 1: 初始化 Git 仓库**

```bash
cd C:/Users/86189
mkdir novel-to-screenplay && cd novel-to-screenplay
git init
git checkout -b feat/project-setup
```

- [ ] **Step 2: 创建 .gitignore**

文件: `.gitignore`
```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Environment
.env

# IDE
.vscode/
.idea/

# Data
backend/data/*.db
backend/data/*.txt

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: 创建 backend/requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
websockets==13.0
pydantic==2.10.0
pydantic-settings==2.7.0
python-dotenv==1.0.1
anthropic==0.40.0
httpx==0.28.0
aiosqlite==0.20.0
jiter==0.8.0
python-multipart==0.0.12
python-docx==1.1.2
pyyaml==6.0.2
pytest==8.3.0
pytest-asyncio==0.24.0
```

- [ ] **Step 4: 创建 backend/.env.example**

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-v4-pro
HITL_CONFIDENCE_THRESHOLD=0.7
MAX_RETRIES=3
DATABASE_PATH=data/state.db
DATA_DIR=data
```

- [ ] **Step 5: 创建 backend/app/config.py**

```python
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_model: str = "deepseek-v4-pro"
    hitl_confidence_threshold: float = 0.7
    max_retries: int = 3
    database_path: str = "data/state.db"
    data_dir: str = "data"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 6: 创建 backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="Novel-to-Screenplay AI Tool", version="0.1.0")

frontend_path = Path(__file__).parent.parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: 创建 backend/tests/conftest.py**

```python
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


@pytest.fixture
def sample_novel_text():
    return """## 第一章：相遇

清晨的阳光洒在竹林的叶尖上。林墨蹲在花圃边，用布满老茧的手拨开泥土。

"墨叔，你为什么从来不离开这个花园？"小禾坐在石凳上问道。

林墨沉默了片刻。"有些根扎得太深了，拔不出来。"

## 第二章：对峙

赵建国穿着不合身的西装走进了花园。"林先生，合同已经准备好了。"

林墨头也没抬。"不卖。"
"""
```

- [ ] **Step 8: 安装依赖并验证**

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows
pip install -r requirements.txt
python -m pytest tests/ -v
```

期望: 0 tests collected (尚无测试文件)

- [ ] **Step 9: 启动 FastAPI 验证**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

访问 `http://localhost:8000/health` 期望返回 `{"status":"ok"}`

- [ ] **Step 10: Commit & Push PR 1**

```bash
git add -A
git commit -m "feat(project): scaffold FastAPI project structure"
git remote add origin <用户仓库URL>
git push -u origin feat/project-setup
# 在 GitHub/GitLab 创建 PR #1 → merge
```

---

### Task 2: LLM Adapter 抽象层 — 协议 + 工厂 (PR 2)

**分支:** `feat/llm-adapter-layer`

**文件:**
- 创建: `backend/app/llm/__init__.py`
- 创建: `backend/app/llm/adapter.py`
- 创建: `backend/app/llm/factory.py`
- 创建: `backend/app/llm/claude_adapter.py`
- 创建: `backend/app/llm/deepseek_adapter.py`
- 创建: `backend/tests/test_adapters.py`

- [ ] **Step 1: 创建 LLMAdapter 协议 + LLMResponse 数据类**

文件: `backend/app/llm/adapter.py`
```python
from typing import Protocol, AsyncIterator, runtime_checkable
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    model: str
    token_usage: dict = field(default_factory=dict)
    parsed_output: dict | None = None


@runtime_checkable
class LLMAdapter(Protocol):
    model_name: str
    context_window: int

    async def complete(
        self,
        prompt: str,
        system_prompt: str = "",
        output_schema: dict | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse: ...

    async def complete_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        output_schema: dict | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]: ...

    def token_count(self, text: str) -> int: ...
```

- [ ] **Step 2: 编写 Adapter 协议测试**

文件: `backend/tests/test_adapters.py`
```python
import pytest
from llm.adapter import LLMAdapter, LLMResponse


class DummyAdapter:
    model_name = "dummy"
    context_window = 4096

    async def complete(self, prompt, system_prompt="", output_schema=None, temperature=0.7):
        return LLMResponse(text='{"key": "value"}', model="dummy", parsed_output={"key": "value"})

    async def complete_streaming(self, prompt, system_prompt="", output_schema=None, temperature=0.7):
        yield '{"key": '
        yield '"value"}'

    def token_count(self, text):
        return len(text) // 4


def test_dummy_adapter_satisfies_protocol():
    adapter = DummyAdapter()
    assert isinstance(adapter, LLMAdapter)


@pytest.mark.asyncio
async def test_dummy_adapter_complete():
    adapter = DummyAdapter()
    response = await adapter.complete("test prompt")
    assert response.text == '{"key": "value"}'
    assert response.parsed_output == {"key": "value"}


@pytest.mark.asyncio
async def test_dummy_adapter_streaming():
    adapter = DummyAdapter()
    chunks = []
    async for chunk in adapter.complete_streaming("test prompt"):
        chunks.append(chunk)
    assert len(chunks) == 2
    assert "".join(chunks) == '{"key": "value"}'
```

- [ ] **Step 3: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_adapters.py -v
```

期望: FAIL (模块未导入，文件未创建)

- [ ] **Step 4: 创建 backend/app/llm/__init__.py**

```python
from .adapter import LLMAdapter, LLMResponse
from .factory import AdapterFactory

__all__ = ["LLMAdapter", "LLMResponse", "AdapterFactory"]
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_adapters.py -v
```

期望: 3 tests PASS

- [ ] **Step 6: 创建 AdapterFactory**

文件: `backend/app/llm/factory.py`
```python
from .adapter import LLMAdapter


class AdapterFactory:
    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, provider: str, adapter_cls: type):
        cls._registry[provider] = adapter_cls

    @classmethod
    def create(cls, provider: str, api_key: str, model: str, **kwargs) -> LLMAdapter:
        if provider not in cls._registry:
            raise ValueError(f"Unknown LLM provider: {provider}. Registered: {list(cls._registry.keys())}")
        return cls._registry[provider](api_key=api_key, model=model, **kwargs)

    @classmethod
    def from_env(cls) -> LLMAdapter:
        from ..config import settings
        return cls.create(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
```

- [ ] **Step 7: 创建 ClaudeAdapter 骨架**

文件: `backend/app/llm/claude_adapter.py`
```python
import json
from typing import AsyncIterator
from .adapter import LLMAdapter, LLMResponse


class ClaudeAdapter:
    model_name: str
    context_window: int = 200000

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.model_name = model
        self.api_key = api_key
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)

    async def complete(self, prompt: str, system_prompt: str = "",
                       output_schema: dict | None = None, temperature: float = 0.7) -> LLMResponse:
        self._ensure_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs = dict(model=self.model_name, max_tokens=8192, messages=messages,
                       temperature=temperature)
        if system_prompt:
            kwargs["system"] = system_prompt
        response = await self._client.messages.create(**kwargs)
        text = response.content[0].text
        parsed = None
        if output_schema:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
        return LLMResponse(text=text, model=self.model_name,
                           token_usage={"input": response.usage.input_tokens,
                                        "output": response.usage.output_tokens},
                           parsed_output=parsed)

    async def complete_streaming(self, prompt: str, system_prompt: str = "",
                                  output_schema: dict | None = None,
                                  temperature: float = 0.7) -> AsyncIterator[str]:
        self._ensure_client()
        messages = [{"role": "user", "content": prompt}]
        kwargs = dict(model=self.model_name, max_tokens=8192, messages=messages, temperature=temperature)
        if system_prompt:
            kwargs["system"] = system_prompt
        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    yield event.delta.text

    def token_count(self, text: str) -> int:
        return len(text) // 4

    @classmethod
    def __init_subclass__(cls, **kwargs):
        pass
```

- [ ] **Step 8: 创建 DeepSeekAdapter 骨架**

文件: `backend/app/llm/deepseek_adapter.py`
```python
import json
import httpx
from typing import AsyncIterator
from .adapter import LLMAdapter, LLMResponse


class DeepSeekAdapter:
    model_name: str
    context_window: int = 1000000

    def __init__(self, api_key: str, model: str = "deepseek-v4-pro"):
        self.model_name = model
        self.api_key = api_key
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.deepseek.com/v1",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                timeout=120.0,
            )

    async def complete(self, prompt: str, system_prompt: str = "",
                       output_schema: dict | None = None, temperature: float = 0.7) -> LLMResponse:
        self._ensure_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.model_name, "messages": messages,
                    "max_tokens": 8192, "temperature": temperature}
        if output_schema:
            payload["response_format"] = {"type": "json_object"}
        response = await self._client.post("/chat/completions", json=payload)
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        parsed = None
        if output_schema:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
        return LLMResponse(text=text, model=self.model_name,
                           token_usage=data.get("usage", {}), parsed_output=parsed)

    async def complete_streaming(self, prompt: str, system_prompt: str = "",
                                  output_schema: dict | None = None,
                                  temperature: float = 0.7) -> AsyncIterator[str]:
        self._ensure_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.model_name, "messages": messages,
                    "max_tokens": 8192, "temperature": temperature, "stream": True}
        if output_schema:
            payload["response_format"] = {"type": "json_object"}
        async with self._client.stream("POST", "/chat/completions", json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta

    def token_count(self, text: str) -> int:
        return len(text) // 4
```

- [ ] **Step 9: 注册 Adapter 并创建工厂测试**

为 `factory.py` 添加注册调用，在文件末尾追加:
```python
from .claude_adapter import ClaudeAdapter
from .deepseek_adapter import DeepSeekAdapter

AdapterFactory.register("claude", ClaudeAdapter)
AdapterFactory.register("deepseek", DeepSeekAdapter)
```

在 `test_adapters.py` 追加:
```python
def test_factory_registry():
    from llm.factory import AdapterFactory
    assert "claude" in AdapterFactory._registry
    assert "deepseek" in AdapterFactory._registry


def test_factory_unknown_provider():
    from llm.factory import AdapterFactory
    import pytest
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        AdapterFactory.create("unknown", "key", "model")
```

- [ ] **Step 10: 运行全量测试**

```bash
cd backend && python -m pytest tests/test_adapters.py -v
```
期望: 5 tests PASS

- [ ] **Step 11: Commit & Push PR 2**

```bash
git checkout -b feat/llm-adapter-layer
git add backend/app/llm/ backend/tests/test_adapters.py
git commit -m "feat(llm): add LLM adapter protocol, factory, Claude and DeepSeek adapters"
git push -u origin feat/llm-adapter-layer
```

---

### Task 3: State Store + 会话管理 (PR 3)

**分支:** `feat/state-store`

**文件:**
- 创建: `backend/app/state/__init__.py`
- 创建: `backend/app/state/models.py`
- 创建: `backend/app/state/repository.py`
- 创建: `backend/app/state/sqlite_store.py`
- 创建: `backend/tests/test_state_store.py`

- [ ] **Step 1: 编写 State 数据模型**

文件: `backend/app/state/models.py`
```python
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any
import uuid


class PipelineStatus(str, Enum):
    CREATED = "created"
    PARSING = "parsing"
    PARSED = "parsed"
    CHAR_EXTRACTING = "char_extracting"
    CHAR_HITL = "char_hitl"
    CHAR_DONE = "char_done"
    SCENE_SEGMENTING = "scene_segmenting"
    SCENE_HITL = "scene_hitl"
    SCENE_DONE = "scene_done"
    SCRIPT_GENERATING = "script_generating"
    SCRIPT_HITL = "script_hitl"
    SCRIPT_DONE = "script_done"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class HITLRequest:
    node: str
    data: dict
    reason: str
    confidence: float = 0.5


@dataclass
class Artifacts:
    chapters: list = field(default_factory=list)
    characters: list = field(default_factory=list)
    scenes: list = field(default_factory=list)
    script_yaml: str | None = None
    adaptation_notes: list = field(default_factory=list)


@dataclass
class PipelineMeta:
    current_agent: str = ""
    progress: float = 0.0
    checkpoint_stack: list[str] = field(default_factory=list)


@dataclass
class SessionState:
    thread_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: PipelineStatus = PipelineStatus.CREATED
    artifacts: Artifacts = field(default_factory=Artifacts)
    pipeline_state: PipelineMeta = field(default_factory=PipelineMeta)
    pending_hitl: HITLRequest | None = None
    errors: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
```

- [ ] **Step 2: 编写 StateRepository 接口**

文件: `backend/app/state/repository.py`
```python
from abc import ABC, abstractmethod
from .models import SessionState


class StateRepository(ABC):
    @abstractmethod
    async def save(self, state: SessionState) -> None: ...

    @abstractmethod
    async def load(self, thread_id: str) -> SessionState | None: ...

    @abstractmethod
    async def list_sessions(self, limit: int = 20) -> list[SessionState]: ...

    @abstractmethod
    async def delete(self, thread_id: str) -> bool: ...
```

- [ ] **Step 3: 编写 SQLite State Store**

文件: `backend/app/state/sqlite_store.py`
```python
import aiosqlite
import json
from pathlib import Path
from .repository import StateRepository
from .models import SessionState, PipelineStatus, Artifacts, HITLRequest, PipelineMeta
from ..config import settings


class SQLiteStateStore(StateRepository):
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.database_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def _get_db(self):
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                thread_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                artifacts_json TEXT DEFAULT '{}',
                pipeline_json TEXT DEFAULT '{}',
                pending_hitl_json TEXT,
                errors_json TEXT DEFAULT '[]',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.commit()
        return db

    async def save(self, state: SessionState) -> None:
        from datetime import datetime, UTC
        state.updated_at = datetime.now(UTC).isoformat()
        db = await self._get_db()
        async with db:
            await db.execute("""
                INSERT OR REPLACE INTO sessions
                (thread_id, status, artifacts_json, pipeline_json,
                 pending_hitl_json, errors_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state.thread_id, state.status.value,
                json.dumps(state.artifacts.__dict__, default=str),
                json.dumps(state.pipeline_state.__dict__),
                json.dumps(state.pending_hitl.__dict__) if state.pending_hitl else None,
                json.dumps(state.errors),
                state.created_at, state.updated_at,
            ))
            await db.commit()

    async def load(self, thread_id: str) -> SessionState | None:
        db = await self._get_db()
        async with db:
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE thread_id = ?", (thread_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_state(row)

    async def list_sessions(self, limit: int = 20) -> list[SessionState]:
        db = await self._get_db()
        async with db:
            cursor = await db.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            return [self._row_to_state(r) for r in rows]

    async def delete(self, thread_id: str) -> bool:
        db = await self._get_db()
        async with db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
            await db.commit()
            return cursor.rowcount > 0

    def _row_to_state(self, row) -> SessionState:
        artifacts_dict = json.loads(row["artifacts_json"])
        artifacts = Artifacts(**artifacts_dict)
        pipeline_dict = json.loads(row["pipeline_json"])
        pipeline_meta = PipelineMeta(**pipeline_dict)
        hitl = None
        if row["pending_hitl_json"]:
            hitl_dict = json.loads(row["pending_hitl_json"])
            hitl = HITLRequest(**hitl_dict)
        return SessionState(
            thread_id=row["thread_id"],
            status=PipelineStatus(row["status"]),
            artifacts=artifacts,
            pipeline_state=pipeline_meta,
            pending_hitl=hitl,
            errors=json.loads(row["errors_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
```

- [ ] **Step 4: 编写 State Store 测试**

文件: `backend/tests/test_state_store.py`
```python
import pytest
from state.sqlite_store import SQLiteStateStore
from state.models import SessionState, PipelineStatus, Artifacts, HITLRequest


@pytest.fixture
async def store(tmp_path):
    db_path = tmp_path / "test.db"
    s = SQLiteStateStore(str(db_path))
    yield s


@pytest.mark.asyncio
async def test_save_and_load(store):
    state = SessionState(
        thread_id="test-001",
        status=PipelineStatus.CREATED,
        artifacts=Artifacts(chapters=[{"index": 1, "title": "第一章"}]),
    )
    await store.save(state)
    loaded = await store.load("test-001")
    assert loaded is not None
    assert loaded.thread_id == "test-001"
    assert loaded.status == PipelineStatus.CREATED
    assert len(loaded.artifacts.chapters) == 1


@pytest.mark.asyncio
async def test_load_nonexistent(store):
    loaded = await store.load("not-found")
    assert loaded is None


@pytest.mark.asyncio
async def test_list_sessions(store):
    for i in range(3):
        await store.save(SessionState(thread_id=f"test-{i:03d}"))
    sessions = await store.list_sessions()
    assert len(sessions) == 3


@pytest.mark.asyncio
async def test_delete(store):
    await store.save(SessionState(thread_id="to-delete"))
    deleted = await store.delete("to-delete")
    assert deleted is True
    assert await store.load("to-delete") is None


@pytest.mark.asyncio
async def test_hitl_persistence(store):
    state = SessionState(
        thread_id="hitl-test",
        status=PipelineStatus.CHAR_HITL,
        pending_hitl=HITLRequest(
            node="char_agent", data={"chars": []}, reason="low_confidence", confidence=0.55),
    )
    await store.save(state)
    loaded = await store.load("hitl-test")
    assert loaded.pending_hitl is not None
    assert loaded.pending_hitl.node == "char_agent"
    assert loaded.pending_hitl.confidence == 0.55
```

- [ ] **Step 5: 运行测试**

```bash
cd backend && python -m pytest tests/test_state_store.py -v
```
期望: 5 tests PASS

- [ ] **Step 6: Commit & Push PR 3**

```bash
git checkout -b feat/state-store
git add backend/app/state/ backend/tests/test_state_store.py backend/app/config.py
git commit -m "feat(state): add SQLite state store with session persistence and HITL support"
git push -u origin feat/state-store
```

---

### Task 4: 章节解析器 + YAML Schema 模型 (PR 4)

**分支:** `feat/chapter-parser`

**文件:**
- 创建: `backend/app/schemas/__init__.py`
- 创建: `backend/app/schemas/screenplay.py`
- 创建: `backend/app/agents/__init__.py`
- 创建: `backend/app/agents/chapter_parser.py`
- 创建: `backend/tests/test_chapter_parser.py`

- [ ] **Step 1: 创建 Pydantic Schema 模型**

文件: `backend/app/schemas/screenplay.py`
```python
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class CharacterRole(str, Enum):
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"
    CAMEO = "cameo"


class RelationType(str, Enum):
    FAMILY = "family"
    FRIEND = "friend"
    RIVAL = "rival"
    ROMANTIC = "romantic"
    MENTOR_STUDENT = "mentor_student"
    COLLEAGUE = "colleague"
    ENEMY = "enemy"
    OTHER = "other"


class CharacterDescription(BaseModel):
    physical: str = ""
    personality: str = ""
    role: CharacterRole


class Relationship(BaseModel):
    target_id: str
    type: RelationType
    note: str = ""


class Character(BaseModel):
    id: str
    name: str
    aliases: list[str] = []
    description: CharacterDescription
    relationships: list[Relationship] = []


class SceneHeading(BaseModel):
    location: str
    time_of_day: Literal["DAWN","MORNING","AFTERNOON","EVENING","NIGHT","LATER","CONTINUOUS"]
    setting_detail: str = ""


class ActionBlock(BaseModel):
    type: Literal["action", "parenthetical"] = "action"
    text: str


class DialogueBlock(BaseModel):
    character_id: str
    emotion: str = ""
    delivery: str = ""
    text: str
    parenthetical: str = ""


class ShotSuggestion(BaseModel):
    type: str
    description: str
    optional: bool = True


class Scene(BaseModel):
    scene_id: str
    chapter: int
    heading: SceneHeading
    characters_present: list[str]
    mood: str = ""
    action: list[ActionBlock]
    dialogue: list[DialogueBlock] = []
    shots: list[ShotSuggestion] = []
    transition: str | None = None


class AdaptationNote(BaseModel):
    scene_id: str | None = None
    chapter: int | None = None
    category: Literal["pacing","dialogue","structure","character","visual"]
    severity: Literal["suggestion","recommendation","warning"]
    content: str


class Stats(BaseModel):
    scene_count: int = 0
    character_count: int = 0
    total_dialogue_blocks: int = 0
    estimated_runtime_minutes: float = 0.0


class Metadata(BaseModel):
    title: str
    original_author: str = ""
    converted_by: str = "AI"
    model: str = ""
    conversion_date: str = ""
    source_chapters: int = 0


class Screenplay(BaseModel):
    schema_version: str = "1.0.0"
    metadata: Metadata
    dramatis_personae: list[Character]
    scenes: list[Scene]
    adaptation_notes: list[AdaptationNote] = []
    stats: Stats = Field(default_factory=Stats)
```

- [ ] **Step 2: 编写 ChapterParser 测试**

文件: `backend/tests/test_chapter_parser.py`
```python
import pytest
from agents.chapter_parser import ChapterParser


def test_parse_chinese_chapter_numbers():
    text = """## 第一章：相遇
竹林晨雾弥漫。

## 第二章：对峙
赵建国走进了花园。

## 第三章：秘密
小禾发现了一本旧日记。"""

    parser = ChapterParser()
    result = parser.parse(text)
    assert len(result) == 3
    assert result[0]["title"] == "第一章：相遇"
    assert result[0]["index"] == 1
    assert result[1]["title"] == "第二章：对峙"
    assert result[2]["title"] == "第三章：秘密"


def test_parse_english_chapters():
    text = """Chapter 1: The Meeting
Morning fog.

Chapter 2: The Confrontation
The door opened."""

    parser = ChapterParser()
    result = parser.parse(text)
    assert len(result) == 2
    assert result[0]["index"] == 1
    assert result[1]["index"] == 2


def test_parse_short_text_returns_single_chapter():
    text = "只有一段文字，没有章节标记。"
    parser = ChapterParser()
    result = parser.parse(text)
    assert len(result) == 1
    assert result[0]["index"] == 1


def test_chapter_has_summary_and_char_count():
    text = "## 第一章\n" + "长" * 1000
    parser = ChapterParser()
    result = parser.parse(text)
    assert "summary" in result[0]
    assert result[0]["char_count"] >= 1000
```

- [ ] **Step 3: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_chapter_parser.py -v
```
期望: FAIL

- [ ] **Step 4: 实现 ChapterParser**

文件: `backend/app/agents/chapter_parser.py`
```python
import re
from pathlib import Path


class ChapterParser:
    CHAPTER_PATTERNS = [
        re.compile(r"#{1,3}\s*第[0-9零一二三四五六七八九十百千]+[章节卷].*", re.MULTILINE),
        re.compile(r"^Chapter\s+\d+.*", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^CHAPTER\s+[IVXLCDM]+.*", re.MULTILINE),
    ]

    def parse(self, text: str) -> list[dict]:
        pattern = self._choose_best_pattern(text)
        if not pattern:
            return [self._make_chapter(text.strip(), 1, "全文")]
        splits = pattern.split(text)
        chapters = []
        index = 1
        buffer = ""
        for segment in splits:
            if pattern.match(segment):
                if buffer.strip():
                    chapters.append(self._make_chapter(buffer.strip(), index))
                    index += 1
                buffer = segment + "\n"
            else:
                buffer += segment
        if buffer.strip():
            chapters.append(self._make_chapter(buffer.strip(), index))
        if len(chapters) < 3 and len(splits) < 3:
            return [self._make_chapter(text.strip(), 1, "全文")]
        return chapters

    def _choose_best_pattern(self, text: str) -> re.Pattern | None:
        for pattern in self.CHAPTER_PATTERNS:
            matches = pattern.findall(text)
            if len(matches) >= 1:
                return pattern
        return None

    def _make_chapter(self, text: str, index: int, title: str = "") -> dict:
        lines = text.strip().split("\n")
        if not title:
            title = lines[0].strip("# ")[:100] if lines else f"第{index}章"
        summary = text[:200].replace("\n", " ")
        return {
            "index": index,
            "title": title,
            "summary": summary,
            "char_count": len(text),
            "text": text,
        }
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_chapter_parser.py -v
```
期望: 4 tests PASS

- [ ] **Step 6: Commit & Push PR 4**

```bash
git checkout -b feat/chapter-parser
git add backend/app/agents/ backend/app/schemas/ backend/tests/test_chapter_parser.py
git commit -m "feat(agents): add chapter parser and screenplay YAML schema models"
git push -u origin feat/chapter-parser
```

---

### Task 5: 角色识别 Agent (PR 5)

**分支:** `feat/character-agent`

**文件:**
- 创建: `backend/app/agents/base.py`
- 创建: `backend/app/agents/character_agent.py`
- 创建: `backend/app/prompts/templates/character_agent/v1/system.txt`
- 创建: `backend/app/prompts/templates/character_agent/v1/user.txt`
- 创建: `backend/tests/test_character_agent.py`

- [ ] **Step 1: 创建 BaseAgent**

文件: `backend/app/agents/base.py`
```python
import json
import re
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any


@dataclass
class AgentResult:
    agent_id: str
    success: bool
    output: dict
    confidence: float
    token_usage: int = 0
    raw_response_ptr: str | None = None
    retries_used: int = 0
    warnings: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    agent_id: str = "base"
    confidence_threshold: float = 0.7
    max_retries: int = 3

    @abstractmethod
    async def run(self, state: dict, llm_adapter) -> AgentResult:
        ...

    @abstractmethod
    def build_prompt(self, state: dict) -> tuple[str, str]:
        ...

    def validate_output(self, raw: dict, state: dict) -> tuple[bool, list[str]]:
        return True, []

    def compute_confidence(self, output: dict, state: dict,
                           schema_compliance: float,
                           self_assessment: float,
                           cross_consistency: float) -> float:
        return schema_compliance * 0.3 + self_assessment * 0.4 + cross_consistency * 0.3

    def _extract_json(self, text: str) -> dict:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
        raise ValueError("No JSON found in response")

    def _check_schema(self, output: dict, required_fields: list[str]) -> float:
        missing = [f for f in required_fields if f not in output]
        if not missing:
            return 1.0
        return max(0.0, 1.0 - len(missing) / len(required_fields))
```

- [ ] **Step 2: 创建 CharacterAgent Prompt 模板**

文件: `backend/app/prompts/templates/character_agent/v1/system.txt`
```
你是一位专业的剧本分析师，擅长从小说文本中识别和提取角色信息。

从以下小说章节中识别所有具名角色。对于每个角色，提取：
1. 姓名（主要称呼）
2. 别称/绰号（小说中出现的所有替代称呼）
3. 外貌描写（年龄、体型、显著特征，如有描述）
4. 性格特征（核心性格、动机、内在冲突）
5. 叙事定位（protagonist/antagonist/supporting/minor/cameo）
6. 与其他角色的关系（目标角色ID、关系类型、简要说明）

关系类型枚举：family, friend, rival, romantic, mentor_student, colleague, enemy, other

输出必须严格符合以下 JSON 格式：
{
  "characters": [
    {
      "id": "c1",
      "name": "角色名",
      "aliases": ["别称1", "别称2"],
      "description": {
        "physical": "外貌描写",
        "personality": "性格描写",
        "role": "protagonist"
      },
      "relationships": [
        {
          "target_id": "c2",
          "type": "friend",
          "note": "关系说明"
        }
      ]
    }
  ],
  "self_assessment": {
    "completeness": 8,
    "character_consistency": 9,
    "format_compliance": 10
  }
}
```

文件: `backend/app/prompts/templates/character_agent/v1/user.txt`
```
请分析以下小说章节，识别所有具名角色：

{chapter_texts}
```

- [ ] **Step 3: 实现 CharacterAgent**

文件: `backend/app/agents/character_agent.py`
```python
from pathlib import Path
from .base import BaseAgent, AgentResult


class CharacterAgent(BaseAgent):
    agent_id = "character_agent"

    def __init__(self):
        self.template_dir = Path(__file__).parent.parent / "prompts" / "templates" / "character_agent" / "v1"
        with open(self.template_dir / "system.txt", encoding="utf-8") as f:
            self.system_template = f.read()
        with open(self.template_dir / "user.txt", encoding="utf-8") as f:
            self.user_template = f.read()

    def build_prompt(self, state: dict) -> tuple[str, str]:
        chapters = state.get("artifacts", {}).get("chapters", [])
        chapter_texts = "\n\n---\n\n".join(
            f"## {c.get('title', 'N/A')}\n{c.get('text', '')[:2000]}"
            for c in chapters
        )
        return self.system_template, self.user_template.format(chapter_texts=chapter_texts)

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        system_prompt, user_prompt = self.build_prompt(state)
        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(user_prompt, system_prompt)
                output = self._extract_json(response.text)
                characters = output.get("characters", [])
                sa = output.get("self_assessment", {})
                schema_score = self._check_schema(output, ["characters", "self_assessment"])
                sa_score = (sa.get("completeness", 5) + sa.get("character_consistency", 5)
                            + sa.get("format_compliance", 5)) / 30.0
                confidence = self.compute_confidence(output, state, schema_score, sa_score, 0.8)
                for i, c in enumerate(characters):
                    if "id" not in c:
                        c["id"] = f"c{i+1}"
                return AgentResult(
                    agent_id=self.agent_id, success=True, output=output,
                    confidence=confidence, token_usage=response.token_usage.get("output", 0),
                    retries_used=attempt,
                )
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return AgentResult(
                        agent_id=self.agent_id, success=False, output={},
                        confidence=0.0, retries_used=attempt,
                        warnings=[str(e)],
                    )
        return AgentResult(agent_id=self.agent_id, success=False, output={}, confidence=0.0)
```

- [ ] **Step 4: 编写测试**

文件: `backend/tests/test_character_agent.py`
```python
import pytest
from unittest.mock import AsyncMock
from llm.adapter import LLMResponse
from agents.character_agent import CharacterAgent


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text='{"characters":[{"id":"c1","name":"林墨","aliases":["老林"],"description":{"physical":"50岁","personality":"沉默","role":"protagonist"},"relationships":[{"target_id":"c2","type":"mentor_student","note":"师徒"}]}],"self_assessment":{"completeness":8,"character_consistency":8,"format_compliance":10}}',
        model="mock", token_usage={"output": 100})
    return adapter


@pytest.mark.asyncio
async def test_character_agent_builds_prompt():
    agent = CharacterAgent()
    state = {"artifacts": {"chapters": [{"title": "第一章", "text": "林墨走进房间。"}]}}
    system, user = agent.build_prompt(state)
    assert "第一章" in user
    assert "林墨" in user


@pytest.mark.asyncio
async def test_character_agent_run(mock_adapter):
    agent = CharacterAgent()
    state = {"artifacts": {"chapters": [{"title": "第一章", "text": "test"}]}}
    result = await agent.run(state, mock_adapter)
    assert result.success
    assert result.output["characters"][0]["name"] == "林墨"
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_character_agent_extracts_json():
    agent = CharacterAgent()
    raw = agent._extract_json('Extra text {"key": "value"} more text')
    assert raw == {"key": "value"}
```

- [ ] **Step 5: 运行测试**

```bash
cd backend && python -m pytest tests/test_character_agent.py -v
```
期望: 3 tests PASS

- [ ] **Step 6: Commit & Push PR 5**

```bash
git checkout -b feat/character-agent
git add backend/app/agents/ backend/app/prompts/ backend/tests/test_character_agent.py
git commit -m "feat(agents): add character extraction agent with Prompt templates"
git push -u origin feat/character-agent
```

---

### Task 6: 场景切分 Agent (PR 6)

**分支:** `feat/scene-agent`

**文件:**
- 创建: `backend/app/agents/scene_agent.py`
- 创建: `backend/app/prompts/templates/scene_agent/v1/system.txt`
- 创建: `backend/app/prompts/templates/scene_agent/v1/user.txt`
- 创建: `backend/tests/test_scene_agent.py`

- [ ] **Step 1: 创建 Prompt 模板**

`system.txt`: 场景切分指令（要求输出 scenes 数组，每项含 scene_id, chapter, heading, characters_present, mood, summary）

`user.txt`: `请将以下章节文本切分为场景单元：\n\n{chapter_texts}\n\n已知角色：{character_list}`

- [ ] **Step 2: 实现 SceneAgent**

文件: `backend/app/agents/scene_agent.py`
```python
from pathlib import Path
from .base import BaseAgent, AgentResult


class SceneAgent(BaseAgent):
    agent_id = "scene_agent"

    def __init__(self):
        base = Path(__file__).parent.parent / "prompts" / "templates" / "scene_agent" / "v1"
        self.system_template = (base / "system.txt").read_text(encoding="utf-8")
        self.user_template = (base / "user.txt").read_text(encoding="utf-8")

    def build_prompt(self, state: dict) -> tuple[str, str]:
        artifacts = state.get("artifacts", {})
        chapters = artifacts.get("chapters", [])
        chapter_texts = "\n\n".join(f"## {c['title']}\n{c.get('text','')[:3000]}" for c in chapters)
        chars = artifacts.get("characters", [])
        char_list = "\n".join(f"- {c['id']}: {c['name']} ({', '.join(c.get('aliases',[]))})" for c in chars)
        return self.system_template, self.user_template.format(
            chapter_texts=chapter_texts, character_list=char_list)

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        system_prompt, user_prompt = self.build_prompt(state)
        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(user_prompt, system_prompt)
                output = self._extract_json(response.text)
                schema_score = self._check_schema(output, ["scenes"])
                cross_score = self._cross_validate(output, state)
                sa = output.get("self_assessment", {})
                sa_score = sum(sa.values()) / max(len(sa) * 10, 1)
                confidence = self.compute_confidence(output, state, schema_score, sa_score, cross_score)
                return AgentResult(
                    agent_id=self.agent_id, success=True, output=output,
                    confidence=confidence, token_usage=response.token_usage.get("output", 0),
                    retries_used=attempt)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return AgentResult(agent_id=self.agent_id, success=False, output={},
                                       confidence=0.0, retries_used=attempt, warnings=[str(e)])
        return AgentResult(agent_id=self.agent_id, success=False, output={}, confidence=0.0)

    def _cross_validate(self, output: dict, state: dict) -> float:
        scenes = output.get("scenes", [])
        if not scenes:
            return 0.5
        char_ids = {c["id"] for c in state.get("artifacts", {}).get("characters", [])}
        errors = 0
        for s in scenes:
            for cid in s.get("characters_present", []):
                if cid not in char_ids:
                    errors += 1
        return max(0.0, 1.0 - errors / max(len(scenes), 1))
```

- [ ] **Step 3: 编写测试 + 运行验证**

测试: mock adapter 返回 scenes JSON，验证 run() 成功且 cross_validate 检测到无效角色 ID 时扣分。

```bash
cd backend && python -m pytest tests/test_scene_agent.py -v
```
期望: PASS

- [ ] **Step 4: Commit & Push PR 6**

```bash
git checkout -b feat/scene-agent
git add backend/app/agents/scene_agent.py backend/app/prompts/templates/scene_agent/ backend/tests/test_scene_agent.py
git commit -m "feat(agents): add scene segmentation agent with cross-validation"
git push -u origin feat/scene-agent
```

---

### Task 7: 剧本生成 Agent (PR 7)

**分支:** `feat/script-agent`

**文件:**
- 创建: `backend/app/agents/script_agent.py`
- 创建: `backend/app/prompts/templates/script_agent/v1/system.txt`
- 创建: `backend/app/prompts/templates/script_agent/v1/user.txt`
- 创建: `backend/tests/test_script_agent.py`

- [ ] **Step 1: 编写 ScriptAgent 测试**

文件: `backend/tests/test_script_agent.py`
```python
import pytest
from unittest.mock import AsyncMock
from llm.adapter import LLMResponse
from agents.script_agent import ScriptAgent

SCRIPT_OUTPUT = '{"scenes":[{"scene_id":"s1","chapter":1,"heading":{"location":"INT. ROOM","time_of_day":"MORNING"},"characters_present":["c1"],"action":[{"text":"He enters."}],"dialogue":[{"character_id":"c1","emotion":"calm","text":"Hello."}]}],"adaptation_notes":[{"category":"pacing","severity":"suggestion","content":"Consider slowing the opening."}],"self_assessment":{"completeness":8,"dialogue_quality":7,"format_compliance":9}}'

@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(text=SCRIPT_OUTPUT, model="mock", token_usage={"output": 200})
    return adapter

@pytest.fixture
def state_with_chars_and_scenes():
    return {
        "artifacts": {
            "chapters": [{"title":"Ch1","text":"..."}],
            "characters": [{"id":"c1","name":"John","aliases":[],"description":{"role":"protagonist"},"relationships":[]}],
            "scenes": [{"scene_id":"s1","chapter":1,"heading":{"location":"ROOM","time_of_day":"MORNING"},"characters_present":["c1"],"mood":"calm","summary":"A man enters."}],
        }
    }

@pytest.mark.asyncio
async def test_script_agent_generates_scenes_and_notes(mock_adapter, state_with_chars_and_scenes):
    agent = ScriptAgent()
    result = await agent.run(state_with_chars_and_scenes, mock_adapter)
    assert result.success
    assert len(result.output["scenes"]) == 1
    assert result.output["scenes"][0]["dialogue"][0]["text"] == "Hello."
    assert len(result.output["adaptation_notes"]) == 1

@pytest.mark.asyncio
async def test_script_agent_fails_on_empty_state():
    agent = ScriptAgent()
    adapter = AsyncMock()
    adapter.complete.side_effect = Exception("API error")
    result = await agent.run({"artifacts": {"chapters":[],"characters":[],"scenes":[]}}, adapter)
    assert not result.success
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_script_agent.py -v
```
期望: FAIL (ScriptAgent 未创建)

- [ ] **Step 3: 实现 ScriptAgent**

文件: `backend/app/agents/script_agent.py`
```python
from pathlib import Path
from .base import BaseAgent, AgentResult


class ScriptAgent(BaseAgent):
    agent_id = "script_agent"

    def __init__(self):
        base = Path(__file__).parent.parent / "prompts" / "templates" / "script_agent" / "v1"
        self.system_template = (base / "system.txt").read_text(encoding="utf-8")
        self.user_template = (base / "user.txt").read_text(encoding="utf-8")

    def build_prompt(self, state: dict) -> tuple[str, str]:
        artifacts = state.get("artifacts", {})
        char_json = str(artifacts.get("characters", []))
        scene_json = str(artifacts.get("scenes", []))
        return self.system_template, self.user_template.format(
            character_table=char_json, scene_list=scene_json)

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        system_prompt, user_prompt = self.build_prompt(state)
        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(user_prompt, system_prompt)
                output = self._extract_json(response.text)
                schema_score = self._check_schema(output, ["scenes"])
                sa = output.get("self_assessment", {})
                sa_score = sum(sa.values()) / max(len(sa) * 10, 1)
                confidence = self.compute_confidence(output, state, schema_score, sa_score, 0.8)
                return AgentResult(
                    agent_id=self.agent_id, success=True, output=output,
                    confidence=confidence, token_usage=response.token_usage.get("output", 0),
                    retries_used=attempt)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return AgentResult(agent_id=self.agent_id, success=False, output={},
                                       confidence=0.0, retries_used=attempt, warnings=[str(e)])
        return AgentResult(agent_id=self.agent_id, success=False, output={}, confidence=0.0)
```

创建 Prompt 模板:
`system.txt`: 剧本生成指令 — 要求输出 scenes 数组（每项含 heading/action/dialogue/shots/transition）、adaptation_notes 数组、self_assessment
`user.txt`: `基于角色表和场景列表生成完整剧本YAML:\n角色表:{character_table}\n场景列表:{scene_list}`

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_script_agent.py -v
```
期望: 2 tests PASS

- [ ] **Step 5: Commit & Push PR 7**

```bash
git checkout -b feat/script-agent
git add backend/app/agents/script_agent.py backend/app/prompts/templates/script_agent/ backend/tests/test_script_agent.py
git commit -m "feat(agents): add script generation agent with adaptation notes"
git push -u origin feat/script-agent
```

---

### Task 8: 校验器 Validator (PR 8)

**分支:** `feat/validator`

**文件:**
- 创建: `backend/app/agents/validator.py`
- 创建: `backend/tests/test_validator.py`

- [ ] **Step 1: 编写 Validator 测试**

文件: `backend/tests/test_validator.py`
```python
import pytest
from agents.validator import Validator


@pytest.fixture
def valid_screenplay():
    return {
        "scenes": [
            {"scene_id":"s1","heading":{"location":"ROOM","time_of_day":"MORNING"},"characters_present":["c1"],"action":[{"text":"test"}],"dialogue":[{"character_id":"c1","text":"hello"}]},
            {"scene_id":"s2","heading":{"location":"PARK","time_of_day":"AFTERNOON"},"characters_present":["c1","c2"],"action":[{"text":"test"}],"dialogue":[]}
        ],
        "dramatis_personae": [
            {"id":"c1","name":"John","description":{"role":"protagonist"}},
            {"id":"c2","name":"Jane","description":{"role":"supporting"}}
        ]
    }


def test_valid_screenplay_passes(valid_screenplay):
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is True
    assert len(result["errors"]) == 0


def test_missing_scene_id_fails():
    validator = Validator()
    result = validator.validate({"scenes": [{"heading":{}}], "dramatis_personae": []})
    assert result["passed"] is False
    assert any("scene_id" in e for e in result["errors"])


def test_invalid_character_reference_fails(valid_screenplay):
    valid_screenplay["scenes"][0]["characters_present"] = ["c99"]
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is False
    assert any("c99" in e for e in result["errors"])


def test_non_sequential_scene_ids_fails():
    validator = Validator()
    screenplay = {
        "scenes": [
            {"scene_id":"s3","heading":{"location":"A","time_of_day":"MORNING"},"characters_present":[],"action":[{"text":"t"}]},
            {"scene_id":"s1","heading":{"location":"B","time_of_day":"NIGHT"},"characters_present":[],"action":[{"text":"t"}]},
        ],
        "dramatis_personae": []
    }
    result = validator.validate(screenplay)
    assert result["passed"] is False
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd backend && python -m pytest tests/test_validator.py -v
```
期望: FAIL

- [ ] **Step 3: 实现 Validator**

文件: `backend/app/agents/validator.py`
```python
class Validator:
    def validate(self, screenplay: dict) -> dict:
        errors, warnings = [], []

        # 1. Schema structural check
        if "scenes" not in screenplay:
            errors.append("Missing required field: scenes")
            return {"passed": False, "errors": errors, "warnings": warnings}

        scenes = screenplay.get("scenes", [])
        characters = screenplay.get("dramatis_personae", [])
        char_ids = {c["id"] for c in characters}

        # 2. Required scene fields
        for scene in scenes:
            sid = scene.get("scene_id")
            if not sid:
                errors.append(f"Scene missing scene_id")
                continue
            if "heading" not in scene:
                errors.append(f"Scene {sid}: missing heading")
            if "location" not in scene.get("heading", {}):
                errors.append(f"Scene {sid}: missing heading.location")
            if "time_of_day" not in scene.get("heading", {}):
                errors.append(f"Scene {sid}: missing heading.time_of_day")
            if "action" not in scene or not scene["action"]:
                errors.append(f"Scene {sid}: missing action")
            # Check character references
            for cid in scene.get("characters_present", []):
                if char_ids and cid not in char_ids:
                    errors.append(f"Scene {sid}: character {cid} not in dramatis_personae")
            for d in scene.get("dialogue", []):
                if char_ids and d.get("character_id", "") not in char_ids:
                    errors.append(f"Scene {sid}: dialogue references unknown character {d.get('character_id')}")

        # 3. Scene ID sequential check
        scene_numbers = []
        for scene in scenes:
            sid = scene.get("scene_id", "")
            if sid.startswith("s") and sid[1:].isdigit():
                scene_numbers.append(int(sid[1:]))
        if scene_numbers and scene_numbers != sorted(set(scene_numbers)):
            warnings.append("Scene IDs are not in sequential order")

        # 4. Dialogue attribution check
        scenes_without_dialogue = [s.get("scene_id","?") for s in scenes if not s.get("dialogue")]
        if len(scenes_without_dialogue) > len(scenes) * 0.8:
            warnings.append(f"{len(scenes_without_dialogue)}/{len(scenes)} scenes without dialogue")

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd backend && python -m pytest tests/test_validator.py -v
```
期望: 4 tests PASS

- [ ] **Step 5: Commit & Push PR 8**

```bash
git checkout -b feat/validator
git add backend/app/agents/validator.py backend/tests/test_validator.py
git commit -m "feat(agents): add screenplay validator with schema, cross-ref, and structural checks"
git push -u origin feat/validator
```

---

### Task 9: Orchestrator — Pipeline + 图引擎 (PR 9)

**分支:** `feat/orchestrator`

**文件:**
- 创建: `backend/app/orchestrator/__init__.py`
- 创建: `backend/app/orchestrator/state_machine.py`
- 创建: `backend/app/orchestrator/pipeline.py`
- 创建: `backend/app/orchestrator/graph_engine.py`
- 创建: `backend/tests/test_pipeline.py`
- 创建: `backend/tests/test_graph_engine.py`

- [ ] **Step 1: 实现 state_machine.py** — `PipelineState` 枚举 + `StateMachine.transition(current, event) -> next_state`
- [ ] **Step 2: 实现 pipeline.py** — Happy Path 线性执行：Parser→CharAgent→SceneAgent→ScriptAgent→Validator
- [ ] **Step 3: 实现 graph_engine.py** — 条件边（confidence < threshold → HITL）、重试循环、回溯
- [ ] **Step 4: 完整测试 → Commit & Push PR 9**

---

### Task 10: API 层 — REST + WebSocket (PR 10)

**分支:** `feat/api-layer`

**文件:**
- 创建: `backend/app/api/__init__.py`
- 创建: `backend/app/api/routes.py`
- 创建: `backend/app/api/websocket.py`

- [ ] **Step 1: routes.py** — 10个REST端点（对应设计文档 §3.1）
- [ ] **Step 2: websocket.py** — WebSocket 连接管理 + 消息路由 + 序列号追踪（支持 resync）
- [ ] **Step 3: 挂载到 main.py → 集成测试 → Commit & Push PR 10**

---

### Task 11: 前端脚手架 + 路由 (PR 11)

**分支:** `feat/frontend-scaffold`

**文件:**
- 创建: `frontend/index.html`
- 创建: `frontend/workspace.html` (占位)
- 创建: `frontend/export.html` (占位)
- 创建: `frontend/css/style.css`
- 创建: `frontend/js/state.js`
- 创建: `frontend/js/websocket.js`

- [ ] **Step 1: index.html** — 首页：文本框粘贴 + 文件上传 + "开始转换"按钮，调用 POST /api/sessions
- [ ] **Step 2: state.js** — 从 URL 提取 thread_id，全局状态管理
- [ ] **Step 3: websocket.js** — WebSocket 客户端，指数退避重连
- [ ] **Step 4: style.css** — 基础样式（暗色主题，工作台布局）
- [ ] **Step 5: 验证 → Commit & Push PR 11**

---

### Task 12: 工作台 UI — Pipeline 进度 + HITL 编辑 (PR 12)

**分支:** `feat/frontend-workspace`

**文件:**
- 修改: `frontend/workspace.html`
- 创建: `frontend/js/pipeline.js`
- 创建: `frontend/js/hitl.js`

- [ ] **Step 1: workspace.html** — 左侧 Pipeline 面板 + 右侧内容主区域
- [ ] **Step 2: pipeline.js** — 进度条更新、阶段状态切换、HITL 节点高亮
- [ ] **Step 3: hitl.js** — 角色卡片编辑器、场景编辑器、确认/跳过/回溯按钮
- [ ] **Step 4: 刷新恢复** — onload → GET /api/sessions/{tid} → 恢复状态
- [ ] **Step 5: 验证 → Commit & Push PR 12**

---

### Task 13: 流式 JSON 渲染 (PR 13)

**分支:** `feat/frontend-streaming`

**文件:**
- 创建: `backend/app/llm/streaming_parser.py`
- 创建: `frontend/js/streaming.js`
- 创建: `backend/tests/test_streaming_parser.py`

- [ ] **Step 1: streaming_parser.py** — 基于 jiter 的增量 JSON 解析器，发出 partial/complete 事件
- [ ] **Step 2: streaming.js** — 前端增量渲染器，逐行显示生成的 YAML
- [ ] **Step 3: 验证 → Commit & Push PR 13**

---

### Task 14: YAML 导出 (PR 14)

**分支:** `feat/yaml-export`

**文件:**
- 修改: `frontend/export.html`
- 修改: `backend/app/api/routes.py` (export 端点)

- [ ] **Step 1: export.html** — "下载 YAML"按钮 + "复制到剪贴板"按钮 + 预览区域
- [ ] **Step 2: GET /api/sessions/{tid}/export** — 返回 YAML 文件流
- [ ] **Step 3: 验证 → Commit & Push PR 14**

---

### Task 15: 端到端集成测试 (PR 15)

**分支:** `feat/integration-test`

**文件:**
- 修改: `backend/tests/test_api.py`

- [ ] **Step 1: test_api.py** — 完整流程测试：
  - POST /api/sessions 创建会话
  - WebSocket 连接验证
  - Pipeline 模拟执行
  - HITL submit 验证
  - GET export 下载验证
- [ ] **Step 2: 运行全量测试**

```bash
cd backend && python -m pytest tests/ -v --cov=app
```
期望: 所有测试 PASS，覆盖率 > 80%

- [ ] **Step 3: Commit & Push PR 15 + README 完善**

---

*实现计划完*

Let me write it now with the actual content. I'll try to fit everything in one Write call.
