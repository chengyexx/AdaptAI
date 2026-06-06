"""校验器 — 规则引擎（非 AI 节点），验证剧本输出的完整性和一致性"""


class Validator:
    def validate(self, screenplay: dict) -> dict:
        errors: list[str] = []
        warnings: list[str] = []

        scenes = screenplay.get("scenes", [])
        characters = screenplay.get("dramatis_personae", [])
        char_ids = {c["id"] for c in characters}

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
            if "action" not in scene or not scene.get("action"):
                errors.append(f"场景 {sid}: 缺少 action")
            for cid in scene.get("characters_present", []):
                if char_ids and cid not in char_ids:
                    errors.append(f"场景 {sid}: 角色 '{cid}' 不在 dramatis_personae 中")
            for d in scene.get("dialogue", []):
                speaker = d.get("character_id", "")
                if char_ids and speaker not in char_ids:
                    errors.append(f"场景 {sid}: 对白引用未知角色 '{speaker}'")

        scene_numbers = []
        for scene in scenes:
            sid = scene.get("scene_id", "")
            if sid.startswith("s") and sid[1:].isdigit():
                scene_numbers.append(int(sid[1:]))
        if scene_numbers:
            expected = list(range(1, len(scene_numbers) + 1))
            if sorted(scene_numbers) != expected:
                warnings.append(f"场景编号不连续: 期望 {expected}，实际 {sorted(scene_numbers)}")

        scenes_with_dialogue = sum(1 for s in scenes if s.get("dialogue"))
        if len(scenes) > 3 and scenes_with_dialogue < len(scenes) * 0.3:
            warnings.append(f"仅 {scenes_with_dialogue}/{len(scenes)} 个场景有对白，可能遗漏对话")

        return {"passed": len(errors) == 0, "errors": errors, "warnings": warnings}
