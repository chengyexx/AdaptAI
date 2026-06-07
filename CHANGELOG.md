# AdaptAI 项目完整更改总结

日期: 2026-06-06
测试: 90/90 pass


## 一、错误修复（3个P0 Bug）

Bug 1 — 相对导入崩溃
文件: backend/app/llm/factory.py 第29行
问题: from ..config import settings 抛出 ImportError: attempted relative import beyond top-level package
根因: main.py 的 sys.path.insert 使 llm 成为顶级包，..config 试图超出包边界
修复: 改为 from config import settings

Bug 2 — Pipeline 双重锁死锁
文件: backend/app/api/routes.py 和 backend/app/orchestrator/pipeline.py
问题: routes.py 在添加后台任务前把 status 设为 PARSING，但 pipeline.execute() 的防重复检查只允许 CREATED/DONE/ERROR/PAUSED，PARSING 不在白名单中，直接 return 不做任何事
修复: 移除 routes.py 中的预置 status 修改，让 Pipeline 自己在 execute() 中切换状态

Bug 3 — UTC 未导入
文件: backend/app/orchestrator/scout_map_pipeline.py Reduce 阶段
问题: from datetime import datetime 漏了 UTC，导致 datetime.now(UTC) 报错 name 'UTC' is not defined
修复: 改为 from datetime import datetime, UTC

Bug 4 — Scout HITL 按钮无响应
文件: frontend/js/app.js
问题: innerHTML 内联 onclick 不可靠；submitScoutHITL 从零构建 characters 数组导致未编辑字段（relationships、first_appearance）丢失
修复: 改为 addEventListener 事件绑定；缓存原始 HITL 数据 _scoutHitlData，提交时合并用户编辑而非覆盖


## 二、前端全面重设计（SPA 单页应用）

重写了整个前端，从原来的 3 个 HTML 文件 + 4 个 JS 文件 + 1 个 CSS 文件，简化为 1 个 HTML 单页应用 + 1 个 JS 模块 + 1 个 CSS 设计系统。前端不再由 FastAPI 提供静态文件服务，改为独立部署（浏览器直接打开即可）。

设计系统命名为 "Neural Interface"——暗色宇宙主题，包含完整的设计令牌（CSS 变量）、玻璃态毛玻璃卡片、渐变品牌色系统、Pipeline 时间线连接线动画、终端风格日志面板、响应式适配。动画系统包含 fadeSlideUp 入场动画、shimmer 加载效果、pulse-ring 脉冲光环、spin 旋转动画。

Pipeline 侧边栏改为 3 步：Scout（全局扫描）、Map（切片转换）、Reduce（校验合并）。每步有独立的状态图标（待执行/进行中/完成/错误），进行中的步骤有脉冲发光动画，完成步骤的连接线变为绿色。

实时终端日志面板在每个 Pipeline 事件时自动追加带时间戳和级别标记（INFO/SUCCESS/WARN/ERROR）的日志行，支持自动滚屏。

HITL 审阅面板：Scout 检查点时弹出完整角色表编辑界面，性格字段和角色定位字段用橙色边框高亮提醒作者重点审阅，角色定位使用下拉选择（主角/反派/配角/龙套/客串），重要度使用数字输入（1-10）。支持"确认设定，继续执行"和"跳过审阅，直接继续"两种操作。

结果面板：Pipeline 完成后自动展示 YAML 输出，支持复制到剪贴板和下载为文件。


## 三、后端架构改造

前后端分离
文件: backend/app/main.py
彻底移除 StaticFiles 静态文件挂载（前端独立部署），添加 CORS 中间件允许跨域访问，新增 GET / 根路径和 /health 健康检查端点。

双模型策略
文件: backend/app/config.py 和 backend/app/llm/factory.py
新增 llm_reasoner_model 配置字段（默认为 deepseek-reasoner），新增 llm_workhorse_temperature 和 llm_reasoner_temperature 超参。AdapterFactory 新增 create_workhorse() 和 create_reasoner() 两个快捷方法，分别创建 deepseek-chat（主力干活模型）和 deepseek-reasoner（R1 推理大脑）适配器。

模型分工规则：Character Agent、Scene Agent、Script Agent 使用 Workhorse（V3，128K 上下文 + Context Caching，极致性价比，结构化输出稳定）；Validator 深度质检使用 Reasoner（R1，强化学习推理，CoT 思维链，检测逻辑矛盾和人物 OOC）。

Scout-Map-Reduce Pipeline（长文本，≥2万字）
新建文件: backend/app/orchestrator/scout_map_pipeline.py
新建文件: backend/app/agents/scout_agent.py
新建文件: backend/app/agents/map_agent.py
新建文件: backend/app/agents/ai_validator.py

Phase 1 (Scout)：LLM 全局通读所有章节，提取全局核心人物表（含 ID、姓名、别称、外貌、性格、角色定位、重要性、关系图谱）和主要地点表，存入 State。完成后触发 SCOUT_HITL 检查点暂停，等待人类审阅角色设定。

Phase 2 (Map)：按章节切片（超 4000 字再切为 2000 字段落），携带经人类确认的全局上下文（角色 ID + 关系 + 地点），逐块发送给 LLM 生成结构化 YAML 场景。每个场景块通过 yaml.safe_load() 解析后，再经 Pydantic ScriptDocument 模型强制校验，校验失败丢弃该块。所有有效场景追加到全局 all_scenes 列表。

Phase 3 (Reduce)：合并所有场景，使用 yaml.dump 生成最终 YAML（含 schema_version、metadata、dramatis_personae、stats 统计信息），然后调用 R1 Reasoner 进行四维度深度推理质检（角色一致性/叙事逻辑/冲突设计/改编质量），CoT 思维链输出审查结果。

HappyPathPipeline + 全节点 HITL（短文本，<2万字）
重写文件: backend/app/orchestrator/pipeline.py
类名从 Pipeline 改为 HappyPathPipeline。新增统一的 _run_agent_step() 执行模式，每个 AI Agent（Character/Scene/Script）执行后自动计算三维复合置信度（Schema 合规度×0.3 + LLM 自评×0.4 + 交叉一致性×0.3），低于阈值（默认 0.7）则暂停并推送 HITL 到前端。支持 CHARACTER_HITL、SCENE_HITL、SCRIPT_HITL 三种检查点，resume_from 参数支持从任意检查点恢复执行。

执行流程：Parser（规则引擎）→ CharacterAgent → [CHAR_HITL ⏸] → SceneAgent → [SCENE_HITL ⏸] → ScriptAgent → [SCRIPT_HITL ⏸] → Validator → COMPLETED。

动态路由器
文件: backend/app/api/routes.py
_should_use_smr(state) 函数根据总字数判断：小于 2 万字走 HappyPathPipeline（快、便宜、连贯性好），大于等于 2 万字走 ScoutMapReducePipeline（切片稳健、大规模适配）。创建会话时 API 返回 pipeline_mode 字段告知前端选择了哪条路。

后端新增 HITL 相关端点：POST /hitl/continue（提交 HITL 编辑并继续执行，适配所有 Agent 的 HITL 检查点），POST /hitl/skip-continue（跳过任何 HITL 审阅并继续）。WebSocket 新增 log 消息类型，后端 Pipeline 每步操作通过 _log() 方法推送实时日志到前端终端面板。

新建 4 个 Prompt 模板文件：scout_agent/v1/system.txt（专业影视策划师，提取角色 ID + 关系图谱 + 地点表），scout_agent/v1/user.txt，map_agent/v1/system.txt（好莱坞编剧 + 数据结构工程师，角色 ID 引用规则，shots 镜头建议，transition 转场方式，mood 情绪基调），map_agent/v1/user.txt（携带全局角色/地点上下文的切片文本）。


## 四、Schema 升级

文件: backend/app/schemas/screenplay.py

ChunkScene 模型升级：新增 mood 字段（场景情绪基调）、shots 字段（镜头建议列表，含 type/description/optional）、transition 字段（转场方式，CUT TO/FADE IN/FADE OUT 等）。

ChunkDialogueLine 模型升级：新增 character_id 字段（优先级高于 character 姓名），用于 LLM 在对话中通过 c1/c2 引用角色。

新增 ChunkShotSuggestion 模型：type（景别类型，wide/close-up/medium/tracking 等）、description（镜头描述）、optional（始终为 true，表示 AI 建议而非强制要求）。

新增 FinalScreenplay 完整模型：schema_version、title、original_author、conversion_date、dramatis_personae（完整角色表）、scenes（场景列表）、adaptation_notes（改编建议）、stats（统计信息，含 scene_count、character_count、total_dialogue_blocks、estimated_runtime_minutes）。

角色体系全面 ID 化：Scout Agent 提取角色时强制分配唯一 ID（c1, c2, c3...），同时输出角色关系图谱（relationships 数组，含 target_id、type、note）。Map Agent 的 context 传入完整角色档案，格式为 "[c1] 林墨 (protagonist, 重要度:8): 沉默寡言 | 关系: friend→c2"。LLM 在对话中使用 character_id: "c1" 而非姓名引用角色，解决别称/绰号的歧义问题。

Pydantic 四层递进校验体系：第一层 yaml.safe_load() 进行 YAML 语法校验，第二层 Pydantic ScriptDocument 进行 Schema 类型/枚举/必填校验，第三层 Validator 规则引擎进行交叉引用/编号连续性/对白归属校验，第四层 R1 Reasoner CoT 进行角色 OOC/叙事逻辑/改编质量深度推理。越往后越贵（R1 消耗是 V3 的 10 倍+），便宜的校验放前面尽早拦截。


## 五、API 端点总览

REST 端点：POST /api/sessions 创建会话（自动调用 ChapterParser 分章，返回 chapters_detected 和 pipeline_mode），GET /api/sessions/{tid} 获取完整会话状态（冷启动恢复），POST /api/sessions/{tid}/start 启动 Pipeline（后台异步执行，立即返回），POST /api/sessions/{tid}/hitl/continue 提交 HITL 编辑并继续，POST /api/sessions/{tid}/hitl/skip-continue 跳过 HITL 并继续，GET /api/sessions/{tid}/export 下载最终 YAML，GET /api/sessions 列出最近会话。

WebSocket /ws/{tid} 消息类型：progress（进度更新，含 agent 和 percent），stage_complete（阶段完成），hitl_pause（HITL 挂起通知，含 data/reason/confidence），error（错误通知，含 agent/message/recoverable），complete（完成通知，含 result.script_yaml），log（终端日志，含 level/message）。


## 六、测试修复

文件: backend/app/orchestrator/__init__.py
导出更新：Pipeline 改为 HappyPathPipeline，新增 ScoutMapReducePipeline。

文件: backend/tests/test_pipeline.py
所有类名和导入从 Pipeline 改为 HappyPathPipeline。

文件: backend/tests/test_frontend_ux.py
CSS 设计令牌检查从 --accent 改为 --brand-500（匹配新设计系统）。

最终结果：90 passed, 0 failed，11 个测试文件全部通过。


## 七、设计文档

文件: docs/yaml-schema-design.md（新建）
完整的 YAML Schema 设计文档，包含每个字段的类型定义、选填说明、设计原因（为什么选 YAML 而非 JSON、为什么角色表集中开篇、为什么用 ID 而非姓名、为什么 shots 标记 optional、为什么对白携带 emotion 和 delivery、为什么需要 schema_version 和 stats），以及 Pydantic 校验模型和四层校验架构。总计 10 条设计理由。

文件: docs/superpowers/（原始设计规格书，3 份）
2026-06-05-novel-to-screenplay-design.md：789 行完整架构设计，包含双模 Orchestrator、Agent 体系、置信度算法、前端架构、错误韧性。
2026-06-05-screenplay-yaml-schema.md：662 行完整 YAML Schema，含 JSON Schema 校验定义和完整 YAML 示例。
2026-06-05-novel-to-screenplay-plan.md：15 个 PR 的 TDD 实现计划，含完整文件结构和测试代码。

## 八、当前能力清单

已完成的能力：3 章以上小说自动分章（ChapterParser 正则识别章节标题），结构化 YAML 输出（含 metadata/stats/dramatis_personae/shots/transitions），角色 ID 化加关系图谱（c1/c2 唯一标识加交叉引用验证），Scout-Map-Reduce 长文本处理（切片转换加全局上下文加 Pydantic 逐块校验），HappyPath 短文本处理（线性 5 步加每节点置信度检查），动态路由（小于 2 万字走 HappyPath，大于等于 2 万字走 SMR），HITL 人机协同（Scout 强制暂停加各 Agent 置信度低于 0.7 自动暂停），双模型策略（V3 干活加 R1 质检），专业编剧 Prompt（好莱坞编剧加数据结构工程师），实时终端日志（WebSocket 推送 INFO/SUCCESS/WARN/ERROR），前端暗色主题 UI（玻璃态加动画加响应式），测试覆盖（90/90 pass）。

待实现：流式 JSON 解析器（jiter 集成，LLM 每吐一个 token 前端即可逐块渲染），文件指针策略（超过 500 字符的大文本字段以文件引用存储而非 SQLite 内联，防止数据库膨胀）。

## 九、启动方式

后端启动命令（在 backend 目录下执行）：uvicorn app.main:app --reload
前端启动：浏览器直接打开 D:\Development\AdaptAI\frontend\index.html
