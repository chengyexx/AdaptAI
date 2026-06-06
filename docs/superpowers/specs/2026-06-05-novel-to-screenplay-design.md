# AI 小说转剧本工具 — 设计规格书

**日期:** 2026-06-05  
**状态:** 草案 — 待审阅  
**作者:** AI 辅助设计，全流程人机协同（HITL）

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构总览](#2-架构总览)
3. [模块一：API 层](#3-模块一api-层)
4. [模块二：Orchestrator — Happy Path + 图引擎 + 状态持久化](#4-模块二orchestrator--happy-path--图引擎--状态持久化)
5. [模块三：Agent 体系](#5-模块三agent-体系)
6. [模块四：LLM Adapter 抽象层](#6-模块四llm-adapter-抽象层)
7. [模块五：前端 + WebSocket HITL 交互](#7-模块五前端--websocket-hitl-交互)
8. [YAML 剧本 Schema](#8-yaml-剧本-schema)
9. [开发流程与 Git 工作流](#9-开发流程与-git-工作流)
10. [测试策略](#10-测试策略)
11. [错误处理与韧性设计](#11-错误处理与韧性设计)
12. [附录：State 载荷管理](#12-附录state-载荷管理)

---

## 1. 项目概述

### 1.1 目标

将 3 个章节以上的小说文本通过 AI 自动转换为结构化剧本 YAML，全流程嵌入 HITL 编辑能力。

### 1.2 核心功能

| 功能 | 说明 |
|------|------|
| **多格式输入** | 支持文本粘贴或 .txt/.md/.docx 文件上传，自动识别章节边界 |
| **AI Pipeline** | 章节解析 → 角色抽取 → 场景切分 → 剧本生成 → 校验 |
| **HITL（人机协同）** | 每个阶段均可编辑；置信度不足时自动暂停等待人工介入 |
| **混合模式** | 默认一键自动转换；可选择"分步精调"逐步查看和编辑 |
| **结构化输出** | YAML 剧本，完整符合 Schema 约束 |
| **改编建议备注** | LLM 生成的改编决策建议 |
| **韧性设计** | 状态持久化、刷新恢复、WebSocket 断线重连 |

### 1.3 技术栈

| 层 | 技术选型 |
|----|----------|
| **后端框架** | Python FastAPI |
| **前端** | 原生 HTML/JS + htmx + Alpine.js（轻量，无构建工具链） |
| **状态持久化** | SQLite（开发/演示），Repository 接口可迁移至 Redis/Postgres |
| **LLM 适配器** | Anthropic SDK (Claude) + DeepSeek SDK；模型无关抽象层 |
| **流式 JSON 解析** | `jiter` 或等价增量 JSON 解析器 |
| **异步** | Python asyncio，FastAPI 原生 WebSocket |
| **容器（可选）** | Docker 统一开发环境 |

---

## 2. 架构总览

### 2.1 顶层架构图

```
                      ┌─────────────────────────────────────┐
                      │           浏览器                      │
                      │  /            /app/{tid}  /export    │
                      └──────────────┬──────────────────────┘
                                     │ HTTP REST + WebSocket
                      ┌──────────────▼──────────────────────┐
                      │         API 层 (FastAPI)             │
                      │   REST 端点 + WebSocket (HITL)       │
                      └──────────────┬──────────────────────┘
                                     │
                      ┌──────────────▼──────────────────────┐
                      │          Orchestrator                 │
                      │   ┌─────────┐  ┌─────────────────┐   │
                      │   │ Happy   │  │  图引擎          │   │
                      │   │ Path    │──▶ (异常/HITL 激活) │   │
                      │   │ Pipeline│  │                 │   │
                      │   └─────────┘  └─────────────────┘   │
                      └──────────────┬──────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
        ┌──────────┐          ┌──────────┐          ┌──────────┐
        │ 章节解析  │          │ 角色     │          │ 场景    │
        │ Parser   │          │ Agent    │          │ Agent   │
        └──────────┘          └──────────┘          └──────────┘
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     │
                      ┌──────────────▼──────────────────────┐
                      │         LLM Adapter 抽象层           │
                      │  ┌─────────┐  ┌──────────┐          │
                      │  │ Claude  │  │ DeepSeek │  ...     │
                      │  │ Adapter │  │ Adapter  │          │
                      │  └─────────┘  └──────────┘          │
                      └─────────────────────────────────────┘
```

### 2.2 双模运行

```
Happy Path（默认，线性流转）:              图引擎（HITL/异常介入）:

  Parser                                     Parser
    │                                          │
    ▼                                          ▼
  CharAgent                                 CharAgent
    │                                          │ (置信度 < 阈值
    ▼                                          │  或用户主动触发)
  SceneAgent                                   ▼
    │                                      [HITL 节点]
    ▼                                          │
  ScriptAgent                                   ▼
    │                                      CharAgent（携带编辑重试）
    ▼                                          │
  Validator                                     ▼
                                          ScriptAgent ──▶ Validator
                                                            │ (校验失败)
                                                            ▼
                                                        [重试循环]
```

### 2.3 设计哲学

- **Happy Path 保持线性**：Parser → CharAgent → SceneAgent → ScriptAgent → Validator，每步成功后自动推进
- **图引擎仅在必要时激活**：低置信度、用户主动暂停、校验失败、异常错误
- **State Store 是唯一事实来源**：每个检查点落盘持久化，每次 HITL 决策可追溯
- **模型无关**：切换 Provider 只需修改一个环境变量

---

## 3. 模块一：API 层

### 3.1 REST 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/sessions` | 创建新会话（上传小说文本/文件） |
| `GET` | `/api/sessions/{thread_id}` | 获取完整会话状态（冷启动恢复） |
| `POST` | `/api/sessions/{thread_id}/start` | 启动 Pipeline 执行 |
| `POST` | `/api/sessions/{thread_id}/pause` | 在下一个检查点暂停 |
| `POST` | `/api/sessions/{thread_id}/resume` | 恢复执行 |
| `POST` | `/api/sessions/{thread_id}/hitl/submit` | 提交 HITL 编辑结果 |
| `POST` | `/api/sessions/{thread_id}/hitl/skip` | 跳过当前 HITL 节点 |
| `POST` | `/api/sessions/{thread_id}/backtrack` | 回退到上一个检查点 |
| `GET` | `/api/sessions/{thread_id}/export` | 下载最终 YAML |
| `GET` | `/api/sessions` | 列出最近会话 |

### 3.2 WebSocket — `/ws/{thread_id}`

消息协议：

```json
// 服务端 → 客户端
{ "type": "progress",        "agent": "char_agent", "percent": 0.4 }
{ "type": "token_stream",    "agent": "script_agent", "chunk": "..." }
{ "type": "hitl_pause",      "agent": "char_agent", "data": {...}, "reason": "low_confidence" }
{ "type": "stage_complete",  "agent": "char_agent", "summary": {...} }
{ "type": "error",           "agent": "scene_agent", "message": "...", "recoverable": true }
{ "type": "complete",        "result": { "script_yaml": "...", "adaptation_notes": [...] } }

// 客户端 → 服务端
{ "type": "resync",          "thread_id": "...", "last_seq": 42 }
{ "type": "hitl_resolved",   "edits": {...} }
{ "type": "request_pause" }
{ "type": "request_skip" }
```

---

## 4. 模块二：Orchestrator — Happy Path + 图引擎 + 状态持久化

### 4.1 核心组件

```
┌──────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                               │
│                                                                   │
│  ┌─────────────────────┐    ┌──────────────────────────────┐     │
│  │   Happy Path Pipeline│    │      图引擎                  │     │
│  │                     │    │                              │     │
│  │  Parser ──▶ Char   │    │  ┌────────┐  ┌───────────┐  │     │
│  │            Agent   │    │  │ 重试   │  │ 分支至    │  │     │
│  │              │     │    │  │ 循环   │  │ HITL      │  │     │
│  │              ▼     │    │  └───┬────┘  └─────┬─────┘  │     │
│  │          Scene     │    │      │             │        │     │
│  │          Agent     │    │  ┌───▼─────────────▼──┐     │     │
│  │              │     │    │  │  条件边             │     │     │
│  │              ▼     │    │  │  (置信度 < 阈值?)   │     │     │
│  │          Script   │    │  └───────────────────┘     │     │
│  │          Agent    │    │                              │     │
│  │              │     │    │  HITL 节点 ◄── 用户编辑   │     │
│  │              ▼     │    │  Validator ◄── 重试      │     │
│  │          Validator│    │                              │     │
│  └─────────────────────┘    └──────────────┬───────────┘     │
│                                            │                  │
│         ┌──────────────────────────────────┘                  │
│         ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐     │
│  │              状态持久化 (Checkpointer)                │     │
│  │                                                       │     │
│  │  thread_id ──▶ {                                      │     │
│  │    current_node: "scene_agent",                       │     │
│  │    state: { chapters: [...], characters: [...], ... },│     │
│  │    checkpoint_stack: [...],   ◄── 支持回溯             │     │
│  │    pending_hitl: { type: "char_review", ... },        │     │
│  │    version: 3                                         │     │
│  │  }                                                    │     │
│  └──────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Pipeline 状态枚举

```python
class PipelineState(Enum):
    CREATED = "created"           # 会话已创建，等待启动
    PARSING = "parsing"           # 章节解析进行中
    PARSED = "parsed"             # 章节识别完成，等待下一步
    CHAR_EXTRACTING = "char_extracting"
    CHAR_HITL = "char_hitl"       # 等待用户审阅角色列表
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
```

### 4.3 State Store 数据结构

```python
class SessionState:
    thread_id: str
    status: PipelineState
    artifacts: Artifacts           # 轻量字段：摘要、元数据
    pipeline_state: PipelineMeta   # 当前节点、进度、检查点栈
    pending_hitl: HITLRequest | None
    errors: list[ErrorInfo]
    created_at: datetime
    updated_at: datetime
    
    # 大文本字段以指针方式存储：
    #   - 完整章节文本 → 文件引用（本地路径或 OSS key）
    #   - LLM 原始响应全文 → 文件引用
    #   - Artifacts 中仅保留摘要和元数据
```

**载荷管理规则：** 超过 500 字符的文本字段，State Store 中仅保留文件指针（如 `data/{thread_id}/chapters/ch1.txt`）。只有摘要和元数据（< 500 字符）内联存储在 SQLite 中。避免多章节长文本导致数据库膨胀和 IO 拖慢。

### 4.4 场景行为矩阵

| 场景 | 行为 |
|------|------|
| **Happy Path** | 线性执行：Parser → CharAgent → SceneAgent → ScriptAgent → Validator |
| **Agent 返回低置信度** | 图引擎插入 HITL 节点，暂停等待用户审阅 |
| **Validator 校验失败** | 图引擎回退到对应 Agent 节点，携带修正提示重试（最多 N 次） |
| **用户点击"查看/编辑"** | 当前节点完成 → 在 HITL 节点暂停，渲染中间结果供编辑 |
| **浏览器刷新 / 断线** | 重连后 REST GET → 从 State Store 恢复完整状态 → 在最后检查点继续 |
| **请求回溯** | 弹出 checkpoint_stack → 恢复到上一检查点 → 从该点重新执行 |

---

## 5. 模块三：Agent 体系

### 5.1 Agent 注册表

```
┌──────────────────────────────────────────────────────────────────────┐
│                        AGENT 注册表                                   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    BaseAgent（抽象基类）                      │    │
│  │                                                              │    │
│  │  + agent_id: str                                             │    │
│  │  + input_schema: JSON Schema     ◄── 严格校验输入             │    │
│  │  + output_schema: JSON Schema    ◄── 结构化输出约束           │    │
│  │  + confidence_threshold: float   ◄── HITL 触发边界            │    │
│  │  + max_retries: int                                          │    │
│  │  ─────────────────────────────────────────────────────────── │    │
│  │  + run(state, llm_adapter) → AgentResult                    │    │
│  │  + validate_output(raw) → ValidationResult                  │    │
│  │  + build_prompt(state) → str           ◄── 每个 Agent 自定    │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                              │                                        │
│         ┌────────────────────┼────────────────────┐                  │
│         ▼                    ▼                    ▼                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐             │
│  │ CharacterAgent│   │  SceneAgent  │   │ ScriptAgent  │             │
│  │              │   │              │   │              │             │
│  │ Prompt:      │   │ Prompt:      │   │ Prompt:      │             │
│  │ "从以下文本  │   │ "将以下章节  │   │ "基于角色表  │             │
│  │  中识别所有  │   │  切分为场景  │   │  和场景列表  │             │
│  │  角色，提取  │   │  单元，标注  │   │  生成剧本    │             │
│  │  姓名/别称/  │   │  地点/时间/  │   │  YAML，包括  │             │
│  │  外貌/性格/  │   │  出场角色/   │   │  对白/动作/  │             │
│  │  关系图谱"   │   │  事件摘要"   │   │  情绪/镜头   │             │
│  └──────────────┘   └──────────────┘   └──────────────┘             │
│                                                                       │
│  ┌──────────────┐   ┌──────────────┐                                 │
│  │ ChapterParser │   │  Validator   │   ◄── 非 AI 节点               │
│  │  (规则引擎)   │   │  (规则+Lint) │                                 │
│  └──────────────┘   └──────────────┘                                 │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Agent 结果契约

```python
@dataclass
class AgentResult:
    agent_id: str
    success: bool
    output: dict              # 结构化输出，符合 output_schema
    confidence: float         # 0.0 ~ 1.0（复合计算，见 §5.3）
    token_usage: int
    raw_response_ptr: str | None  # 文件指针，非内联文本
    retries_used: int
    warnings: list[str]
```

### 5.3 置信度计算

纯文本生成任务无法使用分类概率。采用多维度复合评估：

```
confidence = f(
    schema_compliance × 0.3,      # 确定性：输出是否符合 output_schema？
    self_assessment × 0.4,        # LLM 自评：按 checklist 打分 1-10
    cross_consistency × 0.3       # 确定性：交叉引用验证
)
```

| 维度 | 方法 | 示例 |
|------|------|------|
| **Schema 合规度** | Pydantic / JSON Schema 校验，缺字段扣分 | `script_yaml` 缺少 `dialogue` 字段 → 得分 0.6 |
| **LLM 自评** | 在 System Prompt 末尾注入评分指令："对以下维度 1-10 打分：完整性、角色一致性、格式规范性" | Agent 返回输出时同时携带自评分数 |
| **交叉一致性** | 规则引擎校验：场景中出场角色是否都在角色表中？对白是否归属于已知角色？每章场景数是否合理？ | 场景引用了角色表中不存在的 `id: c12` → 得分 0.5 |

**HITL 触发规则：**

| 条件 | 动作 |
|------|------|
| `confidence < 0.7` | 暂停 → HITL 节点，用户确认/修正 |
| `confidence >= 0.7` | 自动通过，结果写入 State |
| `max_retries` 耗尽 | 暂停 → HITL 节点，附错误诊断信息 |
| 用户主动触发"查看此步" | 当前节点完成后暂停，进入编辑态 |
| `confidence < 0.4` | 标记为"需要人工重写" |

阈值可通过环境变量配置：`HITL_CONFIDENCE_THRESHOLD=0.7`

### 5.4 各 Agent 详细说明

#### ChapterParser（规则引擎，非 AI 节点）

- 通过正则表达式识别章节边界（`第X章`、`Chapter X`、`CHAPTER X`、Markdown 标题）
- 提取章节标题、序号、字符数、摘要（取前 200 字符）
- 返回结构化章节列表；完整文本通过文件指针存储

#### CharacterAgent（角色识别 Agent）

- 从各章文本中识别所有具名角色
- 逐角色提取：姓名、别称、外貌描写、性格特征、叙事定位/重要性
- 构建角色关系图谱（角色 A ↔ 角色 B 关系）
- 输出匹配角色表 Schema

#### SceneAgent（场景切分 Agent）

- 将各章节切分为场景单元
- 逐场景标注：地点、时段、出场角色、事件摘要、情绪基调
- 维持时间顺序，采用章-节层级编号
- 输出匹配场景列表 Schema

#### ScriptAgent（剧本生成 Agent）

- 基于角色表 + 场景列表生成完整剧本 YAML
- 逐场景生成：动作描写、带角色归属的对白、情绪标注
- 生成镜头/导演建议（景别、转场方式）
- 生成改编建议备注（C 级元素）
- 输出匹配完整剧本 YAML Schema

#### Validator（校验器，规则引擎，非 AI 节点）

- Schema 合规：对照 JSON Schema 校验 YAML
- 交叉引用：确认场景中所有角色均存在于角色表中
- 结构检查：确认场景编号连续、无断层
- 对白检查：所有对白均归属于已知角色
- 返回通过/失败，附具体报错信息供 Agent 重试使用

---

## 6. 模块四：LLM Adapter 抽象层

### 6.1 架构

```
┌──────────────────────────────────────────────────────────────┐
│                     LLM ADAPTER 抽象层                         │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              LLMAdapter（抽象协议）                    │    │
│  │                                                      │    │
│  │  + complete(prompt, system_prompt,                   │    │
│  │             output_schema, temperature) → LLMResponse│    │
│  │  + complete_streaming(...) → AsyncIterator[Token]    │    │
│  │  + token_count(text) → int                           │    │
│  │  + model_name: str                                   │    │
│  │  + context_window: int                               │    │
│  └──────────────────────────────────────────────────────┘    │
│                     │                │                        │
│                     ▼                ▼                        │
│  ┌──────────────────────┐  ┌──────────────────────┐         │
│  │  ClaudeAdapter       │  │  DeepSeekAdapter     │         │
│  │                      │  │                      │         │
│  │  - model: claude-    │  │  - model: deepseek-  │         │
│  │    sonnet-4-6        │  │    v4-pro            │         │
│  │  - max_tokens: 8192  │  │  - max_tokens: 8192  │         │
│  │  - provider:         │  │  - provider:         │         │
│  │    Anthropic SDK     │  │    DeepSeek API      │         │
│  └──────────────────────┘  └──────────────────────┘         │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              AdapterFactory                          │    │
│  │                                                      │    │
│  │  + create(provider: str, config: dict) → LLMAdapter │    │
│  │  + from_env() → LLMAdapter  ◄── 读取 .env 自动选择   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Prompt 模板注册中心                       │    │
│  │  templates/                                          │    │
│  │    character_agent/v1/system.txt                     │    │
│  │    character_agent/v1/user.txt                       │    │
│  │    scene_agent/v1/system.txt                         │    │
│  │    ...                                               │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 Provider 切换

`.env` 中一行修改即可：

```env
LLM_PROVIDER=deepseek        # 或 "claude"、"openai"
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-v4-pro
```

```python
# AdapterFactory.from_env() 自动解析并返回正确的 Adapter 实例
adapter = AdapterFactory.from_env()
```

### 6.3 流式 JSON 解析器

当 `complete_streaming` 携带 `output_schema` 参数时，Adapter 将每个 token 输出送入 `StreamingJSONParser`（基于 `jiter` 或等价库）。该解析器：

1. 缓存输入 token 片段
2. 每次收到新 chunk 后尝试增量 JSON.parse
3. 发出 `partial` 事件，携带当前能拼装出的最深合法 JSON 子树
4. 流结束时发出 `complete` 事件，携带完整解析并经过 Schema 校验的对象

这使得前端可以在剧本尚未完全生成时就开始逐行渲染，无需等待完整响应。

### 6.4 结构化输出策略

按 Provider 分别处理：
- **Claude**：使用原生 tool-use / structured-output，传入 JSON Schema 约束
- **DeepSeek**：使用 function-calling 或 JSON-mode prompt 指令
- **通用回退**：从文本响应中后置提取 JSON，再用 Schema 校验

---

## 7. 模块五：前端 + WebSocket HITL 交互

### 7.1 状态同步架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     前端状态架构                                  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                   StateProvider (Context)                 │    │
│  │                                                          │    │
│  │  session: {                                              │    │
│  │    thread_id: "uuid",        ◄── URL 参数 (/app/{tid})   │    │
│  │    status: SessionStatus,                                 │    │
│  │    artifacts: {...},         ◄── 与后端 State 同步        │    │
│  │    progress: float,                                       │    │
│  │    hitl: HITLRequest | null, ◄── 当前编辑断点            │    │
│  │    error: ErrorInfo | null                                │    │
│  │  }                                                        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                    │
│         ┌────────────────────┼────────────────────┐              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │ REST 同步     │   │  WebSocket   │   │ 本地缓存     │         │
│  │ (冷启动恢复)  │   │  (热更新)    │   │ (乐观 UI)    │         │
│  └──────────────┘   └──────────────┘   └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 三种数据通道

| 通道 | 触发时机 | 数据流向 | 用途 |
|------|----------|----------|------|
| **REST** | 页面首次加载 / 刷新 | Server → Client | 从 State Store 恢复完整状态 |
| **REST** | 用户提交 HITL 编辑 | Client → Server | 持久化编辑结果 |
| **WebSocket** | Pipeline 进度推送 | Server → Client | 流式进度、中间结果 |
| **WebSocket** | Token 实时流 | Server → Client | Streaming JSON 逐帧渲染 |
| **WebSocket** | HITL 触发 | Server → Client | 挂起通知 |
| **IndexedDB** | WebSocket 断线间隙 | Client ↔ Client | 乐观缓存，避免空白闪烁 |

### 7.3 刷新恢复流程

```
用户刷新页面 (F5)
        │
        ▼
┌──────────────────┐
│ 1. URL 路由匹配   │   /app/{thread_id} → 提取 thread_id
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. REST 冷启动    │   GET /api/sessions/{thread_id}
│    拉取全量快照   │   ← 返回 State Store 中的 artifacts + pipeline_state
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 3. 状态重组       │   根据 pipeline_state.current_agent 确定当前阶段
│                   │   根据 pending_hitl 是否为 null 判断模式
└────────┬─────────┘
         ▼
    ┌────┴────┐
    ▼         ▼
 pending_hitl    无 HITL
 不为 null        (自动模式)
    │              │
    ▼              ▼
┌─────────┐   ┌──────────────┐
│ 渲染编辑 │   │ 渲染进度条 +  │
│ 界面 +   │   │ 重连 WebSocket│
│ 预填数据 │   │ 继续推送     │
└─────────┘   └──────────────┘
```

### 7.4 WebSocket 断线重连（指数退避）

```
重连间隔: 1s → 2s → 4s → 8s → 上限 30s

每次成功重连后:
  1. 发送: {"type": "resync", "thread_id": "...", "last_seq": 42}
  2. 服务端回放 seq > 42 的所有未确认事件
  3. 前端增量应用错过的所有事件
```

### 7.5 路由与页面布局

```
路由:
  /                        →  首页：上传小说 / 粘贴文本
  /app/{thread_id}         →  工作台：Pipeline 进度 + 中间结果 + YAML 预览
  /app/{thread_id}/export  →  导出页：下载 YAML / 复制到剪贴板

工作台布局 (/app/{thread_id}):

  ┌─────────────────────────────────────────────────────────┐
  │  顶栏：小说标题 | 进度条 (60%) | 当前阶段标签             │
  ├──────────────────────┬──────────────────────────────────┤
  │                      │                                  │
  │  Pipeline 阶段面板    │       内容主区域                  │
  │  (左侧边栏)          │                                  │
  │                      │  ┌──────────────────────────┐   │
  │  ✓ 章节解析          │  │ 角色列表 (可编辑)         │   │
  │  ✓ 角色识别          │  │ ┌────┬────┬────┐        │   │
  │  ● 场景切分 (进行中) │  │ │张三│李四│... │        │   │
  │  ○ 剧本生成          │  │ └────┴────┴────┘        │   │
  │  ○ 校验导出          │  │                          │   │
  │                      │  │ [场景1] 竹林 → 对白预览  │   │
  │  ───────────────     │  │                          │   │
  │  操作:               │  │ 实时流式 YAML 预览       │   │
  │  [跳过] [重试]       │  │                          │   │
  └──────────────────────┴──────────────────────────────┘
```

### 7.6 关键交互时序（HITL 触发）

```
  服务端 ──WS──▶ {"type": "hitl_pause", "node": "char_agent",
                   "data": {"characters": [...], "confidence": 0.55}}

  前端响应:
    1. 左侧边栏：角色识别节点闪烁橙色 HITL 标记
    2. 右侧主区域：渲染角色卡片编辑界面
    3. 每张卡片：姓名/别称/外貌/性格 → 可编辑输入框
    4. 用户修改 → 点击 [确认并继续]
    5. 客户端 → POST /api/sessions/{tid}/hitl/submit
    6. 客户端 → WS send: {"type": "hitl_resolved", "edits": {...}}
    7. 服务端将编辑后的角色数据重新注入 → 继续 Pipeline

  ─────────────────────────────────────────────────────────

  用户在 HITL 编辑时刷新页面:
    → URL 提取 thread_id
    → GET /api/sessions/{tid}
    → 返回 { pipeline_state: {current: "char_agent"}, pending_hitl: {...} }
    → 恢复 HITL 编辑界面，表单预填服务端保存的状态数据
```

---

## 8. YAML 剧本 Schema

详见配套文档：[`2026-06-05-screenplay-yaml-schema.md`](./2026-06-05-screenplay-yaml-schema.md)

### 8.1 Schema 结构概览

```
screenplay
├── metadata          # 标题、作者、转换信息
├── dramatis_personae # 角色表（含特征和关系）
├── scenes            # 核心单元 — 地点、时间、角色、动作、对白
│   ├── heading       # 场景标题（slug line）
│   ├── action        # 动作描写
│   ├── dialogue      # 角色对白块
│   └── shots         # 镜头/导演建议
├── adaptation_notes  # LLM 生成的改编建议
├── stats             # 统计信息
└── schema_version    # Schema 版本号（向前兼容）
```

### 8.2 关键设计决策（理由摘要）

| 决策 | 理由 |
|------|------|
| **选择 YAML 而非 JSON** | 人类可读、支持注释、与剧本写作工具自然兼容 |
| **层级化场景编号** | `act.scene` 或 `chapter.scene` 结构允许局部编辑而不破坏引用 |
| **角色表前置** | "人物表"是剧本传统写法；集中化避免跨场景重复 |
| **`shots` 作为建议而非要求** | LLM 可建议镜头方向，但编剧拥有最终决定权；均标记为 optional |
| **`adaptation_notes` 内联** | 每个场景/章节可携带专属备注，支持针对性修改 |
| **`schema_version`** | 向前兼容：未来 Schema 变更可被检测和迁移 |
| **对白块携带 `emotion`** | 不同于标准剧本格式，情绪标注使表演指导更丰富 |
| **角色表中的关系图谱** | 捕获 LLM 从文本中推断的角色间动态关系，对改编决策有价值 |

---

## 9. 开发流程与 Git 工作流

### 9.1 原则

> 每个小步骤 → commit → 创建 PR → merge。增量推进，可审查，可回滚。

### 9.2 分支策略

```
main
  └── feat/project-setup          # PR 1: 项目脚手架
  └── feat/llm-adapter-layer       # PR 2: LLM Adapter 抽象层
  └── feat/state-store             # PR 3: State Store + 会话管理
  └── feat/chapter-parser          # PR 4: 章节解析器（规则引擎）
  └── feat/character-agent         # PR 5: 角色识别 Agent
  └── feat/scene-agent             # PR 6: 场景切分 Agent
  └── feat/script-agent            # PR 7: 剧本生成 Agent
  └── feat/validator               # PR 8: 校验器
  └── feat/orchestrator            # PR 9: Orchestrator（Pipeline + 图引擎）
  └── feat/api-layer               # PR 10: FastAPI 端点 + WebSocket
  └── feat/frontend-scaffold       # PR 11: 前端脚手架 + 路由
  └── feat/frontend-workspace      # PR 12: 工作台 UI（进度 + HITL）
  └── feat/frontend-streaming      # PR 13: 流式 JSON 渲染
  └── feat/yaml-export             # PR 14: YAML 导出 + 下载
  └── feat/integration-test        # PR 15: 端到端集成测试
```

### 9.3 Commit 规范

```
type(scope): 描述

类型: feat, fix, refactor, test, docs, chore
范围: llm, state, agents, api, frontend, schema, docs

示例:
  feat(llm): 添加 DeepSeekAdapter 流式输出支持
  fix(agents): 修复角色 Agent 重复姓名误判
  docs(schema): 添加剧本 YAML Schema 文档
```

### 9.4 PR 模板

```markdown
## 概述
本次变更的简要描述

## 变更文件
- `path/to/file` — 变更内容与原因

## 验证
- [ ] 测试通过
- [ ] 手动验证步骤
- [ ] 截图（如有 UI 变更）
```

---

## 10. 测试策略

| 层 | 类型 | 范围 |
|----|------|------|
| **LLM Adapters** | 单元 + 集成 | Mock LLM 响应，验证 Adapter 输出格式 |
| **Agents** | 单元 | 给定输入 → 期望正确的 Prompt 构建和输出解析 |
| **ChapterParser** | 单元 | 给定示例小说文本 → 正确的章节边界 |
| **Validator** | 单元 | 给定合法/非法 YAML → 正确的通过/失败 |
| **Orchestrator** | 单元 | Mock Agent，验证状态转换 |
| **API** | 集成 | FastAPI TestClient，端到端会话创建 → 完成 |
| **前端** | 手动 + 可选 E2E | UI 交互流程，刷新恢复 |
| **Schema** | 单元 | 对照 Schema 校验示例 YAML |

---

## 11. 错误处理与韧性设计

### 11.1 错误分类

| 类别 | 处理方式 |
|------|----------|
| **LLM API 错误**（限流、超时） | 指数退避重试（3 次），仍失败则 HITL 暂停附带诊断 |
| **LLM 输出解析错误** | 用更严格的 Prompt 重试（最多 2 次），仍失败则 HITL |
| **Schema 校验错误** | Validator 捕获 → 携带错误上下文重试 ScriptAgent |
| **文件上传错误** | 立即返回错误，不产生任何状态变更 |
| **WebSocket 断连** | 退避重连，通过 REST 回放状态 |
| **State Store 错误** | 快速失败：DB 恢复前阻塞所有 Pipeline 操作 |

### 11.2 优雅降级

- LLM Provider 不可用 → 会话保持在 `CREATED` 状态，通知用户
- 有部分进度 → Provider 恢复后状态可恢复
- 流式输出失败 → 回退到非流式 `complete()` 调用

---

## 12. 附录：State 载荷管理

### 12.1 问题

3 章以上的长篇小说可达数十万字。每次流转时把完整原文塞入 State Store 将导致：

- 数据库膨胀（单行数 MB）
- 序列化/反序列化缓慢
- LLM 上下文窗口被已处理文本浪费

### 12.2 解决方案

**指针/摘要策略：**

```
┌──────────────────────────────────────────────────┐
│                 State Store (SQLite)              │
│                                                   │
│  artifacts.chapters[i]:                           │
│    {                                              │
│      "index": 1,                                  │
│      "title": "第一章：开始",                      │
│      "summary": "15字摘要...",                    │  ← 内联（轻量）
│      "char_count": 3200,                          │
│      "text_ptr": "chapters/ch1_full.txt"          │  ← 指针（文件引用）
│    }                                              │
│                                                   │
│  完整文本存放在磁盘或对象存储上，                   │
│  不进入数据库行。                                  │
└──────────────────────────────────────────────────┘
```

**规则：** 超过 500 字符的文本字段以文件指针存储。仅摘要和元数据（< 500 字符）内联存储在数据库中。

**内存态流转：** Pipeline 执行时，完整章节文本仅为当前 Agent 加载到内存，用后即弃。下一个 Agent 按需从指针重新加载。保持工作集最小化。

---

*设计规格书完*
