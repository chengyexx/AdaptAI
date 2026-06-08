"""Map Agent — 切片转换阶段: 逐块生成 YAML 场景脚本"""

import yaml
import re
from pathlib import Path
from .base import BaseAgent, AgentResult
from schemas.screenplay import ScriptDocument


class MapAgent(BaseAgent):
    """切片转换 Agent — 携带全局上下文，逐块生成 YAML 场景

    输出: 符合 ScriptDocument schema 的 YAML (由 LLM 生成原始 YAML，Pydantic 校验)
    """

    agent_id = "map_agent"
    confidence_threshold = 0.6

    def __init__(self):
        template_dir = (
            Path(__file__).parent.parent
            / "prompts" / "templates" / "map_agent" / "v1"
        )
        self.system_template = (template_dir / "system.txt").read_text(encoding="utf-8")
        self.user_template = (template_dir / "user.txt").read_text(encoding="utf-8")

    def build_prompt(
        self,
        chunk_text: str,
        characters_context: str,
        locations_context: str,
    ) -> tuple[str, str]:
        return self.system_template, self.user_template.format(
            characters_context=characters_context,
            locations_context=locations_context,
            chunk_text=chunk_text,
        )

    async def run_for_chunk(
        self,
        chunk_text: str,
        characters_context: str,
        locations_context: str,
        llm_adapter,
        chunk_index: int = 0,
    ) -> AgentResult:
        """为单个切片生成场景 YAML

        三阶段容错:
          Phase 1 (正常重试): 最多 max_retries 次标准 LLM 调用 + Pydantic 严格校验
          Phase 2 (宽松解析): 从最后一次 LLM 输出中尽力提取场景（填默认值）
          Phase 3 (修复提示): 将上次输出+错误信息发给 LLM 修正格式
        """
        system_prompt, user_prompt = self.build_prompt(
            chunk_text, characters_context, locations_context
        )

        last_raw_text = ""
        last_errors: list[str] = []

        # ── Phase 1: 正常重试 ──
        for attempt in range(self.max_retries):
            try:
                response = await llm_adapter.complete(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )

                yaml_text = self._clean_yaml(response.text)
                last_raw_text = yaml_text
                scenes, parse_errors = self._parse_and_validate(yaml_text)

                if scenes:
                    return AgentResult(
                        agent_id=self.agent_id,
                        success=True,
                        output={
                            "scenes": scenes,
                            "yaml_text": yaml_text,
                            "chunk_index": chunk_index,
                        },
                        confidence=0.85,
                        token_usage=response.token_usage.get("output", 0),
                        retries_used=attempt,
                    )

                last_errors = parse_errors or ["YAML 解析或校验失败"]
                if attempt < self.max_retries - 1:
                    continue

            except Exception as e:
                last_errors = [str(e)]
                if attempt < self.max_retries - 1:
                    continue

        # ── Phase 2: 宽松解析（不额外调 LLM，直接从上次输出提取）──
        if last_raw_text:
            scenes = self._lenient_parse(last_raw_text, chunk_index)
            if scenes:
                return AgentResult(
                    agent_id=self.agent_id,
                    success=True,
                    output={
                        "scenes": scenes,
                        "yaml_text": last_raw_text,
                        "chunk_index": chunk_index,
                    },
                    confidence=0.55,  # 降级标记：宽松校验通过
                    retries_used=self.max_retries,
                    warnings=["宽松解析: 部分字段已自动补全默认值"],
                )

        # ── Phase 3: 修复提示（最后一次 LLM 调用修正格式）──
        if last_raw_text:
            fix_prompt = self._build_fix_prompt(user_prompt, last_raw_text, last_errors)
            try:
                response = await llm_adapter.complete(
                    prompt=fix_prompt,
                    system_prompt=system_prompt,
                )
                yaml_text = self._clean_yaml(response.text)

                # 先宽松解析，不行再用严格校验
                scenes = self._lenient_parse(yaml_text, chunk_index)
                if not scenes:
                    scenes, _ = self._parse_and_validate(yaml_text)

                if scenes:
                    return AgentResult(
                        agent_id=self.agent_id,
                        success=True,
                        output={
                            "scenes": scenes,
                            "yaml_text": yaml_text,
                            "chunk_index": chunk_index,
                        },
                        confidence=0.45,  # 最低置信度：修复后通过
                        retries_used=self.max_retries + 1,
                        warnings=["格式修复: 经修复提示后通过"],
                    )
            except Exception:
                pass

        return AgentResult(
            agent_id=self.agent_id,
            success=False,
            output={"scenes": [], "yaml_text": last_raw_text},
            confidence=0.0,
            retries_used=self.max_retries,
            warnings=last_errors or ["YAML 解析或校验失败"],
        )

    # ═══════════════════════════════════════════════════
    # 清洗 & 校验
    # ═══════════════════════════════════════════════════

    def _clean_yaml(self, text: str) -> str:
        """清理 LLM 输出的 YAML，去除 markdown 标记

        处理多种包裹格式:
          ```yaml ... ```  → 标准 markdown
          ``` ... ```      → 无语言标记
          仅在首尾的 ```   → 防 LLM 格式混乱
        """
        text = text.strip()

        # 去除所有 ``` 包裹（包括嵌套情况）
        while text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # 去掉第一行的 ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        return text

    def _parse_and_validate(self, yaml_text: str) -> tuple[list[dict], list[str] | None]:
        """解析 YAML 并用 Pydantic 校验，返回 (scene dict 列表, 错误信息)

        Returns:
            (scenes, errors) — scenes 为空时 errors 包含失败原因
        """
        errors: list[str] = []

        try:
            raw = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            return [], [f"YAML 语法错误: {e}"]

        if not raw:
            return [], ["YAML 解析结果为空"]

        if isinstance(raw, list):
            return [], ["YAML 输出为列表而非字典，缺少顶层键"]

        if "场景列表" not in raw:
            # 列出顶层键帮助调试
            available = ", ".join(str(k) for k in raw.keys())
            return [], [f"缺少 '场景列表' 键，顶层键: {available}"]

        if not raw["场景列表"]:
            return [], ["场景列表为空"]

        try:
            doc = ScriptDocument(**raw)
            return [s.model_dump() for s in doc.场景列表], None

        except Exception as e:
            # 收集 Pydantic 校验错误详情
            error_msg = str(e)
            # 截断过长的错误信息
            if len(error_msg) > 300:
                error_msg = error_msg[:300] + "..."
            return [], [f"Pydantic 校验失败: {error_msg}"]

    # ═══════════════════════════════════════════════════
    # 降级恢复
    # ═══════════════════════════════════════════════════

    def _lenient_parse(self, yaml_text: str, chunk_index: int = 0) -> list[dict]:
        """宽松解析 — 尽力从 YAML 文本中提取场景，缺失字段自动补默认值

        与 _parse_and_validate 的区别:
          - 不依赖 Pydantic 严格校验
          - 缺失必填字段时自动填充而非失败
          - 跳过完全无法修复的场景条目
        """
        # 先尝试标准 yaml.safe_load
        raw = None
        try:
            raw = yaml.safe_load(yaml_text)
        except yaml.YAMLError:
            pass

        if not raw or not isinstance(raw, dict) or "场景列表" not in raw:
            # 尝试从文本中提取 YAML 块
            raw = self._extract_yaml_block(yaml_text)

        if not raw or "场景列表" not in raw:
            return []

        scenes_raw = raw.get("场景列表", [])
        if not isinstance(scenes_raw, list) or not scenes_raw:
            return []

        scenes = []
        for idx, s in enumerate(scenes_raw):
            if not isinstance(s, dict):
                continue
            repaired = self._repair_scene(s, idx, chunk_index)
            if repaired:
                scenes.append(repaired)

        return scenes

    def _extract_yaml_block(self, text: str) -> dict | None:
        """尝试从自由文本中提取 YAML 场景列表

        处理 LLM 输出为自然语言+嵌入 YAML 的情况。
        """
        # 尝试找 "场景列表:" 并提取到文档末尾或空行
        match = re.search(r'场景列表\s*:\s*\n(\s*-)', text)
        if match:
            # 从 "场景列表:" 开始重建
            rest = text[match.start():]
            try:
                return yaml.safe_load(rest)
            except yaml.YAMLError:
                pass

        # 尝试找所有 "- 场景编号:" 开头的条目并手动构建
        scene_blocks = re.split(r'\n(?=- 场景编号:)', text)
        if len(scene_blocks) > 1:
            scenes = []
            for block in scene_blocks:
                if not block.strip():
                    continue
                try:
                    # 确保以 "- " 开头
                    if not block.strip().startswith("- "):
                        block = "- " + block.strip()
                    parsed = yaml.safe_load(block)
                    if isinstance(parsed, list) and parsed:
                        scenes.append(parsed[0])
                    elif isinstance(parsed, dict):
                        scenes.append(parsed)
                except yaml.YAMLError:
                    continue
            if scenes:
                return {"场景列表": scenes}

        return None

    def _repair_scene(self, scene: dict, idx: int, chunk_index: int = 0) -> dict | None:
        """修复单个场景：为缺失的必填字段填充默认值"""
        # 场景编号 — 必填
        if "场景编号" not in scene or not scene["场景编号"]:
            scene["场景编号"] = f"s{idx + 1}"

        # 来源章节 — 必填，默认用 chunk_index
        if "来源章节" not in scene:
            scene["来源章节"] = chunk_index
        elif scene["来源章节"] is None or scene["来源章节"] == "":
            scene["来源章节"] = chunk_index

        # 场景标题 — 必填 dict，至少需要 地点
        if "场景标题" not in scene or not isinstance(scene["场景标题"], dict):
            scene["场景标题"] = {"地点": "未知", "时段": "白天"}
        else:
            heading = scene["场景标题"]
            if "地点" not in heading or not heading["地点"]:
                heading["地点"] = "未知"
            if "时段" not in heading or not heading["时段"]:
                heading["时段"] = "白天"
            if "场景细节" not in heading:
                heading["场景细节"] = ""

        # 出场角色 — 默认空列表
        if "出场角色" not in scene:
            scene["出场角色"] = []

        # 情绪基调 — 默认空
        scene.setdefault("情绪基调", "")

        # 动作描述 — 默认空列表
        if "动作描述" not in scene:
            scene["动作描述"] = []

        # 对白 — 默认空列表
        if "对白" not in scene:
            scene["对白"] = []

        # 镜头建议 — 默认空列表
        if "镜头建议" not in scene:
            scene["镜头建议"] = []

        # 转场方式 — 默认 None
        scene.setdefault("转场方式", None)

        return scene

    def _build_fix_prompt(
        self, original_user_prompt: str, failed_output: str, errors: list[str]
    ) -> str:
        """构建格式修复提示词：将失败输出和校验错误反馈给 LLM"""
        error_summary = "\n".join(f"  - {e}" for e in errors)
        return (
            f"{original_user_prompt}\n\n"
            f"---\n"
            f"⚠️ 上一次输出格式有误，校验失败。请根据以下错误修正后重新输出：\n\n"
            f"## 校验错误\n{error_summary}\n\n"
            f"## 上一次的输出（参考其内容，但修正格式问题）\n```yaml\n{failed_output[:3000]}\n```\n\n"
            f"## 修正要求\n"
            f"1. 确保顶层包含 '场景列表' 键，值为 YAML 列表\n"
            f"2. 每个场景必须包含: 场景编号(s1,s2...)、来源章节、场景标题(含地点和时段)\n"
            f"3. 使用正确的 YAML 缩进（2空格）\n"
            f"4. 字符串中包含冒号时使用引号包裹\n"
            f"5. 不要嵌套多余的 markdown 代码块\n\n"
            f"请直接输出修正后的完整 YAML："
        )

    async def run(self, state: dict, llm_adapter) -> AgentResult:
        """不直接使用此方法，由 Pipeline 按 chunk 调用 run_for_chunk"""
        raise NotImplementedError("MapAgent 应通过 run_for_chunk() 使用，而非 run()")
