# AdaptAI 后端完整审计报告
生成时间: 2026-06-07
编译状态: 26/26 文件编译通过
测试状态: 90/90 通过
修复状态: P0-1 ✅ P0-2 ✅ P1-1 ✅ P2-1 ✅ P2-2 ✅ P2-3 ✅

================================================================================
一、文件清单
================================================================================

已审查 26 个文件:

  app/main.py                    app/config.py
  app/api/routes.py              app/api/websocket.py
  app/orchestrator/__init__.py   app/orchestrator/pipeline.py
  app/orchestrator/scout_map_pipeline.py
  app/state/models.py            app/state/repository.py
  app/state/sqlite_store.py
  app/llm/__init__.py            app/llm/adapter.py
  app/llm/deepseek_adapter.py    app/llm/claude_adapter.py
  app/llm/factory.py
  app/agents/__init__.py         app/agents/base.py
  app/agents/chapter_parser.py   app/agents/character_agent.py
  app/agents/scene_agent.py      app/agents/script_agent.py
  app/agents/validator.py        app/agents/scout_agent.py
  app/agents/map_agent.py        app/agents/ai_validator.py
  app/schemas/screenplay.py

================================================================================
二、发现的问题
================================================================================

P0 - 必定导致数据丢失或功能错误
-------------------------------------------------------------------------------

[P0-1] HappyPathPipeline Step 1 重复解析导致章丢失
文件: app/orchestrator/pipeline.py, 第 62 行
问题: Step 1 调用 self.parser.parse(state.artifacts.chapters[0]["text"])
      仅重新解析第一章文本并覆盖完整章节列表。
      当用户上传 3 章文本时(create_session 已正确解析为 3 个章节),
      Step 1 覆盖后只剩第一章的子章节, Chapter 2/3 的内容永久丢失。
后果: 后续 Agent (Character/Scene/Script) 拿到的 chapters 列表残缺,
      只基于第 1 章生成剧本。
修复: 删除 Step 1 的整个重解析逻辑。create_session 已经在创建时调用了
      ChapterParser, 章节列表已完整。Pipeline 应直接使用已有数据:
        # 替换第 55-70 行为:
        # Step 1 已由 create_session 完成, 直接标记完成
        state.pipeline_state.checkpoint_stack.append("parser_done")
        state.pipeline_state.progress = 0.2
        await self._persist(state)
        await self._push_progress(tid, "chapter_parser", 0.2)
        await self._push_stage_complete(tid, "chapter_parser")
        await self._log(tid, "success", f"章节已解析: {len(state.artifacts.chapters)} 章")

[P0-2] Validator 校验 Map Agent 输出时字段名不匹配
文件: app/agents/validator.py, 第 40-41 行
问题: Validator.validate() 检查 scene["action"], 但 Map Agent 的场景输出
      遵循 ChunkScene schema, 动作字段名为 "plot_actions"。
      SMR Pipeline 的 _run_reduce 调用了 AIValidator.validate(),
      内部调用了 self.rule_validator.validate(screenplay),
      导致所有 SMR 场景都被标记缺少 action 字段。
条件: 仅在 ScoutMapReducePipeline 触发 (文本 >= 2 万字)。
后果: R1 校验器收到大量虚假错误信号, 可能导致误判剧本质量。
修复: Validator 中同时兼容 "action" 和 "plot_actions":
      # 第 40-41 行改为:
      action_field = scene.get("action") or scene.get("plot_actions", [])
      if not action_field:
          errors.append(f"场景 {sid}: 缺少动作描述")

P1 - 影响正确性但不阻塞运行
-------------------------------------------------------------------------------

[P1-1] SMR Pipeline 中 dead code (无用变量)
文件: app/orchestrator/scout_map_pipeline.py, 第 182-183 行
代码: global_locations = state.pipeline_state.checkpoint_stack if hasattr(state, '_locations') else []
       locations_ctx = ""
问题: hasattr(state, '_locations') 永远为 False (state 是 SessionState dataclass,
      没有 _locations 属性), global_locations 始终为空列表 "[]".
      locations_ctx 始终为 "" 传给 Map Agent, 地点上下文缺失。
修复: 从 state.artifacts 中提取地点信息。
      注意: Scout Agent 提取的 locations 目前未存储到 Artifacts 中,
      需要先在 AIValidator 或 Pipeline 中持久化 locations。

[P1-2] Validator 交叉引用校验对 SMR 场景的 char_id 格式不兼容
文件: app/agents/validator.py, 第 44-48 行
问题: Validator 期望 characters_present 中的值为角色 ID (如 "c1").
      但 Map Agent 的 prompt 要求输出角色引用用 character_id,
      YAML 中 characters_present 可能是角色名字而非 ID.
      如果 Scout 给出的角色 ID 和 Map 输出的角色引用格式不一致,
      校验器会报告大量虚假交叉引用错误。
修复: 统一角色引用格式: Map Agent 的 prompt 明确要求 characters_present
      必须使用 Scout 输出的角色 ID (c1/c2...), 不是姓名。

P2 - 代码质量/维护隐患
-------------------------------------------------------------------------------

[P2-1] httpx.AsyncClient 从未关闭
文件: app/llm/deepseek_adapter.py, 第 20 行 & app/llm/claude_adapter.py
问题: DeepSeekAdapter._client 是懒加载的 httpx.AsyncClient,
      但类没有任何 close/cleanup 方法。uvicorn 热重载时旧实例的
      HTTP 连接泄漏, 长期运行可能导致文件描述符耗尽。
修复: 添加 async def close(self) 方法, 在 Pipeline 完成后或
      应用 shutdown 时调用。

[P2-2] routes.py 中 pipeline_mode 返回值的 key 名不一致
文件: app/api/routes.py, 第 79 行 vs 第 170 行
问题: POST /sessions 返回 "pipeline_mode": "scout-map-reduce" | "simple"
      POST /sessions/{tid}/start 返回 "pipeline_mode": "scout-map-reduce" | "happy-path"
      start 端点用 "happy-path", create_session 用 "simple"。
      前端可能无法正确匹配。
修复: 统一为 "happy-path" 或 "simple"。

[P2-3] HappyPathPipeline 的 script_agent 输出用 json.dumps 而非 yaml.dump
文件: app/orchestrator/pipeline.py, 第 202-203 行
问题: _run_agent_step 中 script_agent 的输出用 json.dumps 序列化,
      与项目名 "将小说转为 YAML 剧本" 不一致。虽然后续 validator
      和后端其他部分不依赖此字段, 但前端展示时看到的是 JSON 非 YAML。
修复: 改为 import yaml; yaml.dump(output, allow_unicode=True)

[P2-4] ai_validator.py 中使用 base.py 的 BaseAgent/AgentResult
文件: app/agents/ai_validator.py
问题: AIValidator 不是 BaseAgent 的子类, 它导入 AgentResult 但从未使用。
      导入行 `from .base import BaseAgent, AgentResult` 中 BaseAgent 空闲。
影响: 无(仅 import 无用符号)。

[P2-5] agents/__init__.py 为空文件
文件: app/agents/__init__.py
问题: 空文件, 不影响运行但不符合项目规范。

================================================================================
三、架构正确性验证
================================================================================

以下模块安全检查全部通过:

  main.py          ✅ CORS 配置正确, 路由挂载正确, WebSocket 端点正确
  config.py        ✅ Settings 继承 BaseSettings, .env 自动加载
  routes.py        ✅ 动态路由逻辑正确, 防重复执行, HITL 端点完整
  websocket.py     ✅ ConnectionManager 线程安全, 序列号机制, dead socket 清理
  state/models.py  ✅ SessionState/Artifacts dataclass 定义完整, UUID 自动生成
  sqlite_store.py  ✅ CREATE TABLE IF NOT EXISTS, upsert 正确, JSON 字段正确序列化
  llm/factory.py   ✅ AdapterFactory 注册机制, 双模型快捷方法正确
  deepseek_adapter ✅ HTTP 调用正确, 流式解析正确, JSON 提取 fallback 正确
  chapter_parser   ✅ 多模式正则, 最小章节阈值, 回退单章节
  character_agent  ✅ ID 自动分配, 三维置信度计算正确
  scene_agent      ✅ 交叉引用校验, ID 自动补全
  script_agent     ✅ prompt 构建中正确传递角色表和场景列表
  scout_agent      ✅ ID 自动分配, 置信度计算正确
  map_agent        ✅ YAML 解析 + Pydantic 校验 + markdown 清理
  ai_validator     ✅ 双阶段校验 (规则引擎 + R1), JSON 提取 fallback
  screenplay.py    ✅ ChunkScene/FinalScreenplay 模型定义完整

================================================================================
四、修复优先级建议
================================================================================

  立即修复 (影响数据正确性):
    1. P0-1: HappyPathPipeline Step 1 删除重复解析
    2. P0-2: Validator 兼容 "plot_actions" 字段

  本周修复:
    3. P1-1: SMR 传递 locations 上下文
    4. P1-2: Map Agent prompt 明确角色 ID 引用

  可延后:
    5. P2-1: httpx.AsyncClient 生命周期管理
    6. P2-2: pipeline_mode key 名称统一
    7. P2-3: script_agent json.dumps → yaml.dump

================================================================================
