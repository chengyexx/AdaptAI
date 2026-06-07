"""校验器 — 规则引擎（非 AI 节点），验证剧本输出的完整性和一致性"""


class Validator:
    """对 Screenplay 输出执行多层次校验

    四个校验维度：
    1. Schema 结构校验 — 必填字段、数据类型
    2. 交叉引用校验 — 场景角色是否存在于角色表中
    3. 结构连续性校验 — 场景编号是否连续、无断层
    4. 对白归属校验 — 所有对白是否归属于已知角色
    """

    def validate(self, screenplay: dict) -> dict:
        """执行全部校验，返回 {passed, errors, warnings}"""
        errors: list[str] = []
        warnings: list[str] = []

        scenes = screenplay.get("scenes", [])
        characters = screenplay.get("dramatis_personae", [])
        char_ids = {c["id"] for c in characters}

        # 1. Schema 结构校验
        if not scenes:
            errors.append("scenes 数组不能为空")

        for scene in scenes:
            sid = scene.get("scene_id", "?")

            if "scene_id" not in scene:
                errors.append("场景缺少 scene_id 字段")
            if "heading" not in scene:
                errors.append(f"场景 {sid}: 缺少 heading")
            else:
                heading = scene["heading"]
                if "location" not in heading:
                    errors.append(f"场景 {sid}: heading 缺少 location")
                if "time_of_day" not in heading:
                    errors.append(f"场景 {sid}: heading 缺少 time_of_day")
            # 兼容 HappyPath ("action") 和 SMR ("plot_actions") 两种输出
            # 注意：不能用 `or`，因为空列表是 falsy 但含义不同
            action_field = scene.get("action")
            if action_field is None:
                action_field = scene.get("plot_actions", [])
            if not action_field:
                errors.append(f"场景 {sid}: 缺少动作块")

            # 2. 交叉引用校验
            for cid in scene.get("characters_present", []):
                if char_ids and cid not in char_ids:
                    errors.append(
                        f"场景 {sid}: 角色 '{cid}' 不在 dramatis_personae 中"
                    )

            # 4. 对白归属校验（兼容 "dialogue" 和 "dialogues"）
            dialogues = scene.get("dialogue")
            if dialogues is None:
                dialogues = scene.get("dialogues", [])
            for d in dialogues:
                speaker = d.get("character_id", "")
                if char_ids and speaker not in char_ids:
                    errors.append(
                        f"场景 {sid}: 对白引用未知角色 '{speaker}'"
                    )

        # 3. 场景编号连续性校验
        scene_numbers = []
        for scene in scenes:
            sid = scene.get("scene_id", "")
            if sid.startswith("s") and sid[1:].isdigit():
                scene_numbers.append(int(sid[1:]))
        if scene_numbers:
            expected = list(range(1, len(scene_numbers) + 1))
            if sorted(scene_numbers) != expected:
                warnings.append(
                    f"场景编号不连续: 期望 {expected}，实际 {sorted(scene_numbers)}"
                )

        # 对白覆盖率检查
        scenes_with_dialogue = sum(
            1 for s in scenes if s.get("dialogue") or s.get("dialogues")
        )
        if len(scenes) > 3 and scenes_with_dialogue < len(scenes) * 0.3:
            warnings.append(
                f"仅 {scenes_with_dialogue}/{len(scenes)} 个场景有对白，可能遗漏对话"
            )

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
