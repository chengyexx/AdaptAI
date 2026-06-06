"""Scout-Map-Reduce Pipeline — 三阶段剧本生成 (含 HITL 检查点)

Phase 1 (Scout):   LLM 全局通读 → 提取人物表+地点表 → ⏸️ HITL Checkpoint → 存入 State
Phase 2 (Map):     按章节切片，携带修正后的全局上下文 → 逐块生成 YAML 场景 → Pydantic 校验
Phase 3 (Reduce):  合并校验 → 拼接最终 YAML → R1 深度推理质检

流程: CREATED → PARSING → SCOUT_HITL(⏸暂停) → CHAR_DONE → SCENE_SEGMENTING → VALIDATING → COMPLETED
"""

from state.models import SessionState, PipelineStatus
from state.sqlite_store import SQLiteStateStore
from agents.scout_agent import ScoutAgent
from agents.map_agent import MapAgent
from agents.ai_validator import AIValidator
from llm.factory import AdapterFactory


class ScoutMapReducePipeline:
    """三阶段 Pipeline — Scout → [HITL Checkpoint] → Map → Reduce"""

    def __init__(self, state_store: SQLiteStateStore | None = None, ws_manager=None):
        self.state_store = state_store or SQLiteStateStore()
        self.ws_manager = ws_manager

    async def execute(self, state: SessionState, resume_from: PipelineStatus | None = None) -> SessionState:
        """执行 Pipeline

        Args:
            state: 会话状态
            resume_from: 从指定阶段恢复执行（用于 HITL 后继续），None 表示从头开始
        """
        from datetime import datetime, UTC

        state.updated_at = datetime.now(UTC).isoformat()
        tid = state.thread_id

        # 确定起始阶段
        start_status = resume_from or state.status

        # 防重复
        if start_status not in (
            PipelineStatus.CREATED,
            PipelineStatus.SCOUT_HITL,   # HITL 审阅后恢复
            PipelineStatus.CHAR_DONE,     # Scout 完成，开始 Map
            PipelineStatus.ERROR,
            PipelineStatus.PAUSED,
        ):
            return state

        # 双模型
        workhorse = AdapterFactory.create_workhorse()
        reasoner = AdapterFactory.create_reasoner()

        try:
            # ═════════════════════════════════════════════
            # Phase 1: Scout — 全局扫描
            # ═════════════════════════════════════════════
            if start_status in (PipelineStatus.CREATED,):
                # 完整执行 Scout
                state = await self._run_scout(state, workhorse, tid, enable_hitl=True)
                if state.status == PipelineStatus.SCOUT_HITL:
                    return state  # ⏸ HITL 暂停，等待人类审阅
                if state.status == PipelineStatus.ERROR:
                    return state

            # Scout 已完成或被跳过

            # ═════════════════════════════════════════════
            # Phase 2: Map — 切片转换
            # ═════════════════════════════════════════════
            state = await self._run_map(state, workhorse, tid)
            if state.status == PipelineStatus.ERROR:
                return state

            # ═════════════════════════════════════════════
            # Phase 3: Reduce — 校验合并
            # ═════════════════════════════════════════════
            state = await self._run_reduce(state, reasoner, tid)

            return state

        except Exception as e:
            state.status = PipelineStatus.ERROR
            state.errors.append({"type": "pipeline_exception", "message": str(e)})
            await self._persist(state)
            await self._push_error(tid, state.pipeline_state.current_agent or "pipeline", str(e))
            return state

    # ═══════════════════════════════════════════════════════
    # Phase 1: Scout
    # ═══════════════════════════════════════════════════════

    async def _run_scout(self, state: SessionState, workhorse, tid: str, enable_hitl: bool = True) -> SessionState:
        """Scout Phase — 全局扫描 + 可选 HITL 检查点"""
        state.status = PipelineStatus.PARSING
        state.pipeline_state.current_agent = "scout_agent"
        state.pipeline_state.progress = 0.05
        await self._persist(state)
        await self._push_progress(tid, "scout_agent", 0.05)
        await self._log(tid, "info", "🔍 Scout Phase: 全局扫描中，提取人物与地点...")

        scout = ScoutAgent()
        scout_result = await scout.run(
            {"artifacts": {"chapters": state.artifacts.chapters}},
            workhorse,
        )

        if not scout_result.success:
            state.errors.append({"agent": "scout_agent", "warnings": scout_result.warnings})
            state.status = PipelineStatus.ERROR
            await self._persist(state)
            await self._push_error(tid, "scout_agent", "全局扫描失败")
            return state

        # 提取结果
        global_characters = scout_result.output.get("characters", [])
        global_locations = scout_result.output.get("locations", [])

        state.artifacts.characters = global_characters
        char_count = len(global_characters)
        loc_count = len(global_locations)

        state.pipeline_state.progress = 0.15
        await self._persist(state)
        await self._push_progress(tid, "scout_agent", 0.15)
        await self._log(tid, "success", f"全局扫描完成: {char_count} 个角色, {loc_count} 个地点")

        # ⏸️ HITL Checkpoint
        if enable_hitl and char_count > 0:
            state.status = PipelineStatus.SCOUT_HITL
            state.pending_hitl = None  # 清空旧的
            await self._persist(state)

            # 推送 HITL 到前端
            if self.ws_manager:
                await self.ws_manager.send_hitl_pause(
                    tid, "scout_agent",
                    data={
                        "characters": global_characters,
                        "locations": global_locations,
                    },
                    reason="请审阅 AI 提取的角色与地点设定，确认或修改后继续",
                    confidence=scout_result.confidence,
                )
            await self._log(tid, "warn", "⏸ Scout 检查点: 请在前端审阅角色与地点设定")
            return state

        # 无 HITL（小文本或禁用）→ 直接标记完成
        state.status = PipelineStatus.CHAR_DONE
        await self._persist(state)
        await self._push_stage_complete(tid, "scout_agent")
        return state

    # ═══════════════════════════════════════════════════════
    # Phase 2: Map
    # ═══════════════════════════════════════════════════════

    async def _run_map(self, state: SessionState, workhorse, tid: str) -> SessionState:
        """Map Phase — 携带全局上下文，逐块生成 YAML 场景"""
        state.status = PipelineStatus.SCENE_SEGMENTING
        state.pipeline_state.current_agent = "map_agent"
        state.pipeline_state.progress = 0.2
        await self._persist(state)
        await self._push_progress(tid, "map_agent", 0.2)
        await self._log(tid, "info", "📝 Map Phase: 逐块生成 YAML 场景脚本...")

        # 构建全局上下文（含角色 ID + 关系）
        character_lines = []
        for c in state.artifacts.characters:
            rels = c.get("relationships", [])
            rel_text = ""
            if rels:
                rel_text = " | 关系: " + ", ".join(
                    f"{r.get('type','?')}→{r.get('target_id','?')}" for r in rels[:3]
                )
            character_lines.append(
                f"- [{c.get('id','?')}] {c.get('name','?')} "
                f"({c.get('role','?')}, 重要度:{c.get('importance','?')}): "
                f"{c.get('description',{}).get('personality','?')}{rel_text}"
            )
        characters_ctx = "\n".join(character_lines)
        global_locations = state.pipeline_state.checkpoint_stack if hasattr(state, '_locations') else []
        locations_ctx = ""  # 简化：从 characters 中提取的地点信息有限

        # 切片
        chapters = state.artifacts.chapters
        chunks = self._slice_chapters(chapters)

        map_agent = MapAgent()
        all_scenes = []
        total_chunks = len(chunks)

        for idx, (chunk_label, chunk_text) in enumerate(chunks):
            chunk_progress = 0.2 + (0.6 * (idx + 1) / max(total_chunks, 1))
            await self._push_progress(tid, "map_agent", chunk_progress)

            if total_chunks > 1:
                await self._log(tid, "info", f"处理 {chunk_label} ({idx + 1}/{total_chunks})...")

            result = await map_agent.run_for_chunk(
                chunk_text=chunk_text,
                characters_context=characters_ctx,
                locations_context=locations_ctx,
                llm_adapter=workhorse,
                chunk_index=idx,
            )

            if result.success:
                scenes = result.output.get("scenes", [])
                all_scenes.extend(scenes)
                if total_chunks > 1:
                    await self._log(tid, "success", f"{chunk_label}: +{len(scenes)} 场景")
            else:
                await self._log(tid, "warn", f"{chunk_label} 失败: {'; '.join(result.warnings)}")
                state.errors.append({
                    "agent": "map_agent", "chunk": chunk_label, "warnings": result.warnings,
                })

            state.pipeline_state.progress = chunk_progress
            await self._persist(state)

        state.artifacts.scenes = all_scenes
        state.pipeline_state.progress = 0.8
        await self._persist(state)
        await self._push_progress(tid, "map_agent", 0.8)
        await self._push_stage_complete(tid, "map_agent")
        await self._log(tid, "success", f"Map Phase 完成: 共 {len(all_scenes)} 个场景")

        if not all_scenes:
            state.errors.append({"type": "map_empty", "message": "所有切片均未生成有效场景"})
            state.status = PipelineStatus.ERROR
            await self._persist(state)
            await self._push_error(tid, "map_agent", "所有切片均未生成有效场景")

        return state

    # ═══════════════════════════════════════════════════════
    # Phase 3: Reduce
    # ═══════════════════════════════════════════════════════

    async def _run_reduce(self, state: SessionState, reasoner, tid: str) -> SessionState:
        """Reduce Phase — 合并 + Pydantic + R1 深度校验"""
        state.status = PipelineStatus.VALIDATING
        state.pipeline_state.current_agent = "validator"
        state.pipeline_state.progress = 0.85
        await self._persist(state)
        await self._push_progress(tid, "validator", 0.85)
        await self._log(tid, "info", "✅ Reduce Phase: 合并校验 + R1 深度推理质检...")

        all_scenes = state.artifacts.scenes

        # 生成最终 YAML（含元数据+统计）
        from datetime import datetime, UTC
        import yaml

        total_dialogues = sum(len(s.get("dialogues", [])) for s in all_scenes)
        char_count = len(state.artifacts.characters)
        scene_count = len(all_scenes)

        final_output = {
            "schema_version": "1.0.0",
            "title": state.artifacts.chapters[0].get("title", "未命名") if state.artifacts.chapters else "未命名",
            "original_author": "",
            "conversion_date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "dramatis_personae": state.artifacts.characters,
            "scenes": all_scenes,
            "adaptation_notes": state.artifacts.adaptation_notes,
            "stats": {
                "scene_count": scene_count,
                "character_count": char_count,
                "total_dialogue_blocks": total_dialogues,
                "estimated_runtime_minutes": round(scene_count * 2.0, 1),
            },
        }
        state.artifacts.script_yaml = yaml.dump(
            final_output,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

        # AI 深度校验
        characters_info = "\n".join(
            f"- {c.get('name','?')}: {c.get('description',{}).get('personality','?')}"
            for c in state.artifacts.characters[:15]
        )
        scenes_info = "\n".join(
            f"- {s.get('scene_id','?')}: {s.get('heading',{}).get('location','?')}"
            for s in all_scenes[:15]
        )

        ai_validator = AIValidator()
        screenplay = {"scenes": all_scenes, "dramatis_personae": state.artifacts.characters}
        validation = await ai_validator.validate(
            screenplay=screenplay,
            characters_info=characters_info,
            scenes_info=scenes_info,
            script_yaml=state.artifacts.script_yaml,
            adaptation_notes=state.artifacts.adaptation_notes,
            reasoner_adapter=reasoner,
        )

        state.artifacts.adaptation_notes.extend(validation.get("warnings", []))

        if validation["passed"]:
            state.status = PipelineStatus.COMPLETED
            state.pipeline_state.progress = 1.0
            await self._log(tid, "success", f"校验通过 (置信度: {validation.get('confidence', 0):.0%})")
        else:
            state.errors.extend([{"type": "validation", "message": e} for e in validation.get("errors", [])])
            state.status = PipelineStatus.ERROR
            await self._log(tid, "warn", f"校验未通过: {len(validation.get('errors', []))} 个问题")

        await self._persist(state)

        if state.status == PipelineStatus.COMPLETED:
            await self._push_complete(tid, state)
        else:
            await self._push_error(tid, "validator", "; ".join(validation.get("errors", [])))

        return state

    # ═══════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _slice_chapters(chapters: list) -> list[tuple[str, str]]:
        chunks = []
        for chapter in chapters:
            text = chapter.get("text", "")
            title = chapter.get("title", f"第{chapter.get('index', '?')}章")
            if len(text) <= 4000:
                chunks.append((title, text))
            else:
                paragraphs = text.split("\n")
                current = ""
                part = 1
                for para in paragraphs:
                    if len(current) + len(para) > 2000 and current:
                        chunks.append((f"{title} (第{part}部分)", current.strip()))
                        part += 1
                        current = para
                    else:
                        current += "\n" + para if current else para
                if current.strip():
                    chunks.append((f"{title} (第{part}部分)", current.strip()))
        return chunks

    async def _persist(self, state):
        try:
            await self.state_store.save(state)
        except Exception:
            pass

    async def _push_progress(self, tid, agent, percent):
        if self.ws_manager:
            try:
                await self.ws_manager.send_progress(tid, agent, percent)
            except Exception:
                pass

    async def _push_stage_complete(self, tid, agent):
        if self.ws_manager:
            try:
                await self.ws_manager.send_stage_complete(tid, agent, {"agent": agent})
            except Exception:
                pass

    async def _push_error(self, tid, agent, message):
        if self.ws_manager:
            try:
                await self.ws_manager.send_error(tid, agent, message, recoverable=True)
            except Exception:
                pass

    async def _push_complete(self, tid, state):
        if self.ws_manager:
            try:
                await self.ws_manager.send_complete(tid, {
                    "thread_id": state.thread_id,
                    "status": state.status.value,
                    "script_yaml": state.artifacts.script_yaml,
                    "characters": state.artifacts.characters,
                    "scenes": state.artifacts.scenes,
                })
            except Exception:
                pass

    async def _log(self, tid, level, message):
        if self.ws_manager:
            try:
                await self.ws_manager._broadcast(tid, {
                    "type": "log",
                    "level": level,
                    "message": message,
                })
            except Exception:
                pass
