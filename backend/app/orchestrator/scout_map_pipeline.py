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
from .base_pipeline import BasePipeline


class ScoutMapReducePipeline(BasePipeline):
    """三阶段 Pipeline — Scout → [HITL Checkpoint] → Map → Reduce"""

    def __init__(self, state_store: SQLiteStateStore | None = None, ws_manager=None):
        super().__init__(state_store, ws_manager)

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
        total_chars = sum(c.get("char_count", 0) for c in state.artifacts.chapters)
        await self._log(tid, "info", f"🔍 Scout Phase: {len(state.artifacts.chapters)} 章节, 约 {total_chars} 字符, 调用 LLM 中...")

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
        state.artifacts.locations = global_locations
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
        # 构建地点上下文
        location_lines = []
        locs = state.artifacts.locations
        for loc in locs:
            location_lines.append(
                f"- [{loc.get('id','?')}] {loc.get('name','?')} "
                f"({loc.get('type','?')}): {loc.get('description','?')[:60]}"
            )
        locations_ctx = "\n".join(location_lines) if location_lines else "(无地点数据)"

        # 切片
        chapters = state.artifacts.chapters
        chunks = self._slice_chapters(chapters)

        map_agent = MapAgent()
        all_scenes = []
        total_chunks = len(chunks)

        # 追踪篇章边界：记录每个原始章节对应哪些场景编号范围
        chapter_boundaries: list[dict] = []  # [{title, scene_start_idx}, ...]
        _last_chapter_idx = None

        for idx, (chunk_label, chunk_text, chapter_idx) in enumerate(chunks):
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
                # 追踪篇章边界：新章节开始时记录
                if chapter_idx != _last_chapter_idx:
                    chapter_boundaries.append({
                        "title": (
                            state.artifacts.chapters[chapter_idx - 1].get("title", f"第{chapter_idx}章")
                            if 1 <= chapter_idx <= len(state.artifacts.chapters)
                            else f"第{chapter_idx}章"
                        ),
                        "scene_start": len(all_scenes),  # 0-based, before extend
                        "chapter_idx": chapter_idx,
                    })
                    _last_chapter_idx = chapter_idx
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

        # 全局场景编号重编排：每个 chunk 独立从 s1 编号，合并后统一重排
        for i, scene in enumerate(all_scenes):
            scene["场景编号"] = f"s{i + 1}"

        # 存储篇章边界信息供 Reduce 阶段使用
        state.artifacts.chapter_boundaries = chapter_boundaries

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

        # 构建篇章边界提示（供 R1 理解多篇章结构）
        boundaries = state.artifacts.chapter_boundaries
        chapter_hint_lines = ["## 篇章结构说明"]
        if len(boundaries) <= 1:
            chapter_hint_lines.append("本剧本为单一连续篇章。")
        else:
            chapter_hint_lines.append(f"本剧本包含 {len(boundaries)} 个独立篇章，各篇章之间可能存在时间线跳跃和角色状态变化，这是正常的：")
            for i, b in enumerate(boundaries):
                start = b["scene_start"]
                end_scene_idx = boundaries[i + 1]["scene_start"] if i + 1 < len(boundaries) else len(all_scenes)
                chapter_hint_lines.append(
                    f"  篇章{i + 1}「{b['title']}」: 场景 s{start + 1} 至 s{end_scene_idx}"
                    f"（共 {end_scene_idx - start} 个场景）"
                )
            chapter_hint_lines.append("跨篇章的时间线矛盾、角色状态变化不应被标记为 critical。")
        chapter_hint = "\n".join(chapter_hint_lines)

        # 生成最终 YAML（含元数据+统计）
        from datetime import datetime, UTC
        import yaml

        total_dialogues = sum(len(s.get("对白", [])) for s in all_scenes)
        char_count = len(state.artifacts.characters)
        scene_count = len(all_scenes)

        final_output = {
            "格式版本": "1.0.0",
            "剧本标题": state.artifacts.chapters[0].get("title", "未命名") if state.artifacts.chapters else "未命名",
            "原著作者": "",
            "转换日期": datetime.now(UTC).strftime("%Y-%m-%d"),
            "角色表": self._localize_characters(state.artifacts.characters),
            "篇章结构": [{
                "篇章": b["title"],
                "起始场景": f"s{b['scene_start'] + 1}",
            } for b in boundaries] if len(boundaries) > 1 else [],
            "场景列表": all_scenes,
            "改编说明": state.artifacts.adaptation_notes,
            "统计信息": {
                "场景数量": scene_count,
                "角色数量": char_count,
                "对白总数": total_dialogues,
                "预估时长分钟": round(scene_count * 2.0, 1),
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
            f"- {s.get('场景编号','?')}: {s.get('场景标题',{}).get('地点','?')}"
            for s in all_scenes[:15]
        )

        ai_validator = AIValidator()
        screenplay = {"场景列表": all_scenes, "角色表": state.artifacts.characters}
        validation = await ai_validator.validate(
            screenplay=screenplay,
            characters_info=characters_info,
            scenes_info=scenes_info,
            script_yaml=state.artifacts.script_yaml,
            adaptation_notes=state.artifacts.adaptation_notes,
            reasoner_adapter=reasoner,
            chapter_hint=chapter_hint,
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
    # 角色表中文化
    # ═══════════════════════════════════════════════════════

    # 中英文枚举映射表
    _ROLE_MAP = {
        "protagonist": "主角", "antagonist": "反派",
        "supporting": "配角", "minor": "龙套", "cameo": "客串",
    }
    _RELATION_MAP = {
        "family": "家人", "friend": "朋友", "rival": "对手",
        "romantic": "恋人", "mentor_student": "师徒",
        "colleague": "同事", "enemy": "敌人", "other": "其他",
        "subordinate": "下属", "mentor": "导师",
        "potential_opponent": "潜在对手", "potential_ally": "潜在盟友",
        "potential_love_interest": "潜在恋爱对象",
    }

    @staticmethod
    def _localize_characters(characters: list[dict]) -> list[dict]:
        """将角色表 key 和枚举值转为纯中文，方便人类阅读"""
        localized = []
        for char in characters:
            desc = char.get("description", {}) or {}
            localized.append({
                "编号": char.get("id", ""),
                "姓名": char.get("name", ""),
                "别名": char.get("aliases", []),
                "外貌": desc.get("physical", ""),
                "性格": desc.get("personality", ""),
                "角色身份": ScoutMapReducePipeline._ROLE_MAP.get(
                    desc.get("role", ""), desc.get("role", "")
                ),
                "重要度": char.get("importance", ""),
                "关系": [
                    {
                        "关联角色": r.get("target_id", ""),
                        "关系": ScoutMapReducePipeline._RELATION_MAP.get(
                            r.get("type", ""), r.get("type", "")
                        ),
                        "说明": r.get("note", ""),
                    }
                    for r in char.get("relationships", [])
                ],
                "首次出场": char.get("first_appearance", ""),
            })
        return localized

    @staticmethod
    def _slice_chapters(chapters: list) -> list[tuple[str, str, int]]:
        """切片章节，返回 (标题, 文本, 章节序号)

        章节序号 1-based，对应原始 chapters 列表中的 index 字段。
        用于在 Reduce 阶段追踪篇章边界，向 R1 提供跨篇章上下文。
        """
        chunks: list[tuple[str, str, int]] = []
        for chapter in chapters:
            text = chapter.get("text", "")
            title = chapter.get("title", f"第{chapter.get('index', '?')}章")
            chapter_idx = chapter.get("index", 1)  # 1-based
            if len(text) <= 4000:
                chunks.append((title, text, chapter_idx))
            else:
                paragraphs = text.split("\n")
                current = ""
                part = 1
                for para in paragraphs:
                    if len(current) + len(para) > 2000 and current:
                        chunks.append((f"{title} (第{part}部分)", current.strip(), chapter_idx))
                        part += 1
                        current = para
                    else:
                        current += "\n" + para if current else para
                if current.strip():
                    chunks.append((f"{title} (第{part}部分)", current.strip(), chapter_idx))
        return chunks
