# AdaptAI — 小说转剧本

将小说文本通过 AI 自动转换为结构化分镜头剧本，全流程嵌入人工审阅编辑能力。

## 核心流程

输入小说文本（粘贴或上传 .txt/.md/.docx）后，Pipeline 自动完成五步转换：

1. **章节解析** — 正则识别章节边界，提取标题和正文
2. **角色识别** — LLM 抽取具名角色，构建外貌、性格、关系图谱
3. **场景切分** — 按时间和地点的显著变化将章节切分为独立场景单元
4. **剧本生成** — 基于角色表和场景骨架生成完整剧本，含动作描写、对白、镜头建议
5. **质量校验** — 规则引擎扫描 Schema 和交叉引用，R1 推理模型做角色 OOC 和叙事逻辑深度审查

每步均可配置 HITL 检查点——AI 置信度低于阈值时自动暂停，等待人工审阅修改后继续。

对于超过 2 万字的较长文本，Pipeline 自动切换为 Scout-Map-Reduce 三阶段模式：先全局扫描提取角色和地点，再逐块生成场景，最后合并校验。

## 快速启动

环境要求：Python 3.10+

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 编辑 .env，填入 LLM API Key
uvicorn app.main:app --reload --port 8000
```

`.env` 中可配置的关键参数：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_PROVIDER` | LLM 提供商 | `deepseek` |
| `LLM_API_KEY` | API 密钥 | 无，必须填写 |
| `LLM_MODEL` | 主力干活模型 | `deepseek-chat` |
| `LLM_REASONER_MODEL` | R1 推理校验模型 | `deepseek-reasoner` |
| `HITL_CONFIDENCE_THRESHOLD` | HITL 触发置信度阈值 | `0.7` |
| `MAX_RETRIES` | Agent 最大重试次数 | `3` |

前端不需要构建——直接用浏览器打开 `frontend/index.html`，或通过任意静态文件服务托管 `frontend/` 目录。

## 项目结构

```
AdaptAI/
├── backend/
│   ├── app/
│   │   ├── api/              # REST 端点 + WebSocket 推送
│   │   │   ├── routes.py     #   会话创建/启动/暂停/HITL/导出
│   │   │   └── websocket.py  #   Pipeline 进度 + 流式 Token 推送
│   │   ├── orchestrator/     # Pipeline 调度引擎
│   │   │   ├── pipeline.py            #   线性五步流程（短文本）
│   │   │   └── scout_map_pipeline.py  #   三阶段流程（长文本）
│   │   ├── agents/           # AI Agent + 规则引擎
│   │   │   ├── chapter_parser.py    #   正则章节边界检测
│   │   │   ├── character_agent.py   #   角色识别与关系图谱
│   │   │   ├── scene_agent.py       #   场景切分与交叉验证
│   │   │   ├── script_agent.py     #   完整剧本生成
│   │   │   ├── scout_agent.py       #   全局扫描（长文本专用）
│   │   │   ├── map_agent.py        #   逐块场景生成（长文本专用）
│   │   │   ├── validator.py        #   规则引擎四维校验
│   │   │   └── ai_validator.py    #   R1 深度推理质检
│   │   ├── llm/              # LLM Adapter 抽象层
│   │   │   ├── adapter.py           #   Protocol 定义
│   │   │   ├── deepseek_adapter.py  #   DeepSeek（兼容 OpenAI 协议）
│   │   │   ├── claude_adapter.py    #   Anthropic Claude
│   │   │   └── factory.py          #   工厂 + 双模型快捷创建
│   │   ├── state/            # 状态持久化
│   │   │   ├── models.py           #   SessionState 数据模型
│   │   │   └── sqlite_store.py     #   SQLite 实现（aiosqlite）
│   │   ├── schemas/          # Pydantic 数据模型
│   │   │   └── screenplay.py       #   剧本 Schema（全中文字段）
│   │   ├── prompts/          # Prompt 模板库（版本化）
│   │   │   └── templates/<agent>/v1/
│   │   │       ├── system.txt
│   │   │       └── user.txt
│   │   └── config.py         # Pydantic Settings 配置
│   ├── tests/                # 测试（目前 18 个用例）
│   ├── requirements.txt
│   ├── .env.example
│   └── AUDIT.md              # 代码审计报告
├── frontend/                 # SPA 前端（零构建工具链）
│   ├── index.html            #   主页面（Landing + Workspace）
│   ├── reader.html           #   双栏原著-剧本对照阅读器（Vue 3）
│   ├── js/
│   │   ├── app.js            #   状态管理 + API + UI 渲染
│   │   ├── pipeline.js       #   Pipeline 步骤图标
│   │   └── streaming.js      #   Token 流实时渲染
│   └── css/
│       └── style.css         #   暗色文学主题
└── docs/                     # 设计文档
    ├── yaml-schema-specification.md   #   YAML Schema 规格说明
    └── design-system.md               #   前端设计令牌
```

## 技术选型

| 层 | 选择 | 原因 |
|----|------|------|
| 后端框架 | FastAPI + asyncio | 原生异步，WebSocket 支持 |
| 状态持久化 | SQLite（aiosqlite） | 零配置，Repository 接口可迁移至 Redis/Postgres |
| LLM | DeepSeek（主力 + R1） | chat 干活，reasoner 质检，按 token 成本分工 |
| AI 编排 | 自建 Pipeline | 不用 LangChain，保持对执行流程的完全控制 |
| 数据校验 | Pydantic v2 | Schema 层强类型约束 |
| 前端 | 原生 JS + Vue 3 CDN | 零构建，HTML 文件直接可用 |
| 测试 | pytest + pytest-asyncio | 异步测试原生支持 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/sessions` | 创建会话，上传小说（文本/文件） |
| `GET` | `/api/sessions/{id}` | 获取会话完整状态 |
| `POST` | `/api/sessions/{id}/start` | 启动 Pipeline |
| `POST` | `/api/sessions/{id}/hitl/continue` | 提交 HITL 编辑，继续执行 |
| `POST` | `/api/sessions/{id}/hitl/skip-continue` | 跳过 HITL，直接继续 |
| `GET` | `/api/sessions/{id}/export` | 导出最终 YAML 剧本 |
| `GET` | `/api/sessions` | 列出历史会话 |
| `DELETE` | `/api/sessions/{id}` | 删除会话 |
| `WS` | `/ws/{id}` | Pipeline 进度 + Token 流推送 |

## 运行测试

```bash
cd backend
pytest -v
```

## 设计文档

- [YAML Schema 规格说明](docs/yaml-schema-specification.md) — 逐字段定义与设计原因
- [设计规格书](docs/superpowers/specs/2026-06-05-novel-to-screenplay-design.md) — 完整架构设计
- [实现计划](docs/superpowers/plans/2026-06-05-novel-to-screenplay-plan.md) — 开发路线

## 设计原则

**模型无关。** 切换 LLM 提供商只需改 `.env` 中的一行。代码通过 Adapter 协议抽象了所有供应商差异。

**渐进校验。** 四层递进：YAML 语法 → Pydantic Schema → 规则引擎交叉引用 → R1 深度推理。越贵的校验越靠后，便宜的先拦截。

**人机协同。** 不是"AI 全自动，人只管结果"。每个关键节点都预留了人工编辑入口，置信度不够就停下来等人。

**状态可恢复。** 所有 Pipeline 状态落盘持久化。浏览器关了、后端崩了，重开就能从断点继续。

**中文原生。** 字段名、枚举值、校验信息全部中文。LLM Prompt、Pydantic 模型、前端渲染、YAML 输出统一使用同一套命名，不存在翻译映射层。

**演示视频**：
[点击这里观看  AdaptAI  完整功能介绍](【七牛云 x XENGINEER 暑期实训营-第三批次-题目三】 https://www.bilibili.com/video/BV16XE76vEYt/?share_source=copy_web&vd_source=dbbde7a85366f1693f082df34280afcd)
