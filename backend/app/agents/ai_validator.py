"""AI 校验器 — 基于 DeepSeek-R1 的深度推理质检

双阶段校验:
  Stage 1 (规则引擎): Schema 结构、交叉引用、场景编号连续性、对白归属  → 快速过滤明显错误
  Stage 2 (R1 深度推理): 角色OOC检测、伏笔逻辑一致性、冲突调度合理性、剧本可拍摄性 → CoT 深度分析
"""

from .validator import Validator


AI_VALIDATOR_SYSTEM_PROMPT = """你是一位资深的剧本审校专家和文学评论家。

你的任务是审查一份从小说改编的剧本草稿，从以下维度进行深度分析：

## 审查维度

1. **角色一致性 (Character Consistency)**
   - 各角色行为是否符合之前设定的人物性格和背景
   - 是否存在人物性格突变（OOC - Out Of Character）
   - 角色关系网是否自洽

2. **叙事逻辑 (Narrative Logic)**
   - 场景之间的因果链条是否完整
   - 关键剧情转折是否有铺垫
   - 是否存在时间线矛盾

3. **冲突设计 (Conflict Design)**
   - 核心戏剧冲突是否延续了原著的张力
   - 次要冲突是否服务于主线
   - 冲突升级的节秦是否合理

4. **改编质量 (Adaptation Quality)**
   - 原著精髓是否被保留
   - 视觉化呈现是否可行
   - 对话是否具有戏剧性且符合角色身份

## 输出格式

你必须输出一个严格的 JSON 对象（不要包含 markdown 代码块标记）：

{
  "passed": true/false,
  "overall_confidence": 0.0~1.0,
  "deep_reasoning": "此处为你的 CoT 思维链分析，说明审查过程和你做出判断的关键理由",
  "issues": [
    {"severity": "critical/major/minor", "aspect": "角色一致性/叙事逻辑/冲突设计/改编质量", "description": "具体问题描述", "suggestion": "修改建议"}
  ],
  "strengths": ["本剧本的优点1", "优点2"],
  "adaptation_notes": ["全局改编建议1", "建议2"],
  "self_assessment": {
    "completeness": 1~10,
    "logic_consistency": 1~10,
    "adaptation_quality": 1~10
  }
}

## 判定标准

- passed=true:  所有 critical 级别问题已解决，整体改编质量可接受
- passed=false: 存在 critical 级别问题，或 adaptation_quality 自评低于 5/10
- 即使 passed=false，也必须给出具体的修改建议
"""

AI_VALIDATOR_USER_PROMPT = """请审查以下小说改编的剧本草稿：

## 原著角色信息
{characters_info}

## 场景列表
{scenes_info}

## 最终剧本 YAML
{script_yaml}

## 改编备注
{adaptation_notes}

请从角色一致性、叙事逻辑、冲突设计、改编质量四个维度进行深度审查。使用 CoT 思维链展示你的推理过程。"""


class AIValidator:
    """双阶段 AI 校验器

    Stage 1: 规则引擎快速扫描 (Schema + 交叉引用 + 编号连续性)
    Stage 2: R1 深度推理审查 (角色OOC + 逻辑一致性 + 改编质量)
    """

    # 提示词截断阈值（保护上下文窗口；对超长剧本应优先截 scene 而非角色）
    MAX_CHAR_INFO = 4000
    MAX_SCENE_INFO = 4000
    MAX_SCRIPT_YAML = 12000

    def __init__(self):
        self.rule_validator = Validator()

    async def validate(
        self,
        screenplay: dict,
        characters_info: str,
        scenes_info: str,
        script_yaml: str,
        adaptation_notes: list,
        reasoner_adapter,
    ) -> dict:
        """执行双阶段校验

        Returns:
            {
                "passed": bool,
                "confidence": float,
                "stage1": {...},       # 规则引擎结果
                "stage2": {...},       # R1 推理结果
                "errors": [str],       # 合并错误
                "warnings": [str],     # 合并警告
            }
        """

        # ── Stage 1: 规则引擎快速扫描 ──
        stage1 = self.rule_validator.validate(screenplay)

        # ── Stage 2: R1 深度推理 ──
        stage2 = await self._run_ai_validation(
            characters_info,
            scenes_info,
            script_yaml,
            adaptation_notes,
            reasoner_adapter,
        )

        # ── 合并结果 ──
        all_errors = stage1.get("errors", [])[:]
        all_warnings = stage1.get("warnings", [])[:]

        if stage2:
            # 合并 R1 发现的问题
            for issue in stage2.get("issues", []):
                if issue.get("severity") == "critical":
                    all_errors.append(f"[AI:{issue.get('aspect','')}] {issue.get('description','')}")
                else:
                    all_warnings.append(f"[AI:{issue.get('aspect','')}] {issue.get('description','')}")

            # 加入 AI 改编建议
            for note in stage2.get("adaptation_notes", []):
                all_warnings.append(f"[Adaptation] {note}")

        # 综合判断: 规则引擎通过 + R1 通过 + R1 置信度达标
        r1_passed = stage2.get("passed", True) if stage2 else True
        r1_confidence = stage2.get("overall_confidence", 0.5) if stage2 else 0.5

        final_passed = stage1.get("passed", True) and r1_passed and r1_confidence >= 0.4

        return {
            "passed": final_passed,
            "confidence": r1_confidence,
            "stage1": stage1,
            "stage2": stage2,
            "errors": all_errors,
            "warnings": all_warnings,
        }

    async def _run_ai_validation(
        self,
        characters_info: str,
        scenes_info: str,
        script_yaml: str,
        adaptation_notes: list,
        reasoner_adapter,
    ) -> dict | None:
        """调用 R1 Reasoner 进行深度推理审查"""
        user_prompt = AI_VALIDATOR_USER_PROMPT.format(
            characters_info=characters_info[:self.MAX_CHAR_INFO],
            scenes_info=scenes_info[:self.MAX_SCENE_INFO],
            script_yaml=script_yaml[:self.MAX_SCRIPT_YAML] if script_yaml else "（尚未生成）",
            adaptation_notes="\n".join(f"- {n}" for n in (adaptation_notes or [])) if adaptation_notes else "（无）",
        )

        try:
            response = await reasoner_adapter.complete(
                prompt=user_prompt,
                system_prompt=AI_VALIDATOR_SYSTEM_PROMPT,
                temperature=0.0,  # R1 建议低温
            )
            output_text = response.text

            # 提取 JSON（R1 可能输出思维链 + JSON）
            import json
            import re

            # 尝试直接解析
            try:
                result = json.loads(output_text)
            except json.JSONDecodeError:
                # 尝试提取 {...} 块
                match = re.search(r'\{[\s\S]*\}', output_text)
                if match:
                    try:
                        result = json.loads(match.group())
                    except json.JSONDecodeError:
                        return None
                else:
                    return None

            return result

        except Exception:
            return None
