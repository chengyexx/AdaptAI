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

        scenes = screenplay.get("场景列表", [])
        characters = screenplay.get("角色表", [])
        char_ids = {c["id"] for c in characters}

        # 1. Schema 结构校验
        if not scenes:
            errors.append("场景列表 数组不能为空")

        for scene in scenes:
            sid = scene.get("场景编号", "?")

            if "场景编号" not in scene:
                errors.append("场景缺少 场景编号 字段")
            if "场景标题" not in scene:
                errors.append(f"场景 {sid}: 缺少 场景标题")
            else:
                heading = scene["场景标题"]
                if "地点" not in heading:
                    errors.append(f"场景 {sid}: 场景标题 缺少 地点")
                if "时段" not in heading:
                    errors.append(f"场景 {sid}: 场景标题 缺少 时段")
            # 兼容 HappyPath ("动作列表") 和 SMR ("动作描述") 两种输出
            action_field = scene.get("动作列表")
            if action_field is None:
                action_field = scene.get("动作描述", [])
            if not action_field:
                errors.append(f"场景 {sid}: 缺少动作块")

            # 2. 交叉引用校验
            for cid in scene.get("出场角色", []):
                if char_ids and cid not in char_ids:
                    errors.append(
                        f"场景 {sid}: 角色 '{cid}' 不在 角色表 中"
                    )

            # 4. 对白归属校验（兼容单复数两种写法）
            dialogues = scene.get("对白", [])
            for d in dialogues:
                speaker = d.get("角色编号", "")
                if char_ids and speaker not in char_ids:
                    errors.append(
                        f"场景 {sid}: 对白引用未知角色 '{speaker}'"
                    )

        # 3. 场景编号连续性校验
        scene_numbers = []
        for scene in scenes:
            sid = scene.get("场景编号", "")
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
            1 for s in scenes if s.get("对白")
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
