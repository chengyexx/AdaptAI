# AdaptAI 剧本 YAML Schema 设计文档

> 版本: 1.0.0 | 日期: 2026-06-06

---

## 一、设计目标

将小说文本转换为影视工业可用的标准化剧本格式。Schema 设计遵循三个原则：

1. **拍摄导向（Production-Ready）**：每个字段都为实际拍摄服务，而非文学分析
2. **人机可读（Human & Machine Readable）**：YAML 格式对编剧友好，同时结构化程度足以被工具链解析
3. **最小完整原则（Minimal Yet Complete）**：不填无意义字段，不遗漏拍摄必需信息

---

## 二、完整 Schema

```yaml
# AdaptAI 剧本 YAML Schema v1.0.0
# 根节点
scenes:
  - scene_id: "s1"                    # 场景唯一编号，全局递增
    chapter: 1                         # 来源章节号
    heading:
      location: "EXT. 废弃工厂"        # INT./EXT. + 具体地点
      time_of_day: "NIGHT"             # DAY | NIGHT | DAWN | DUSK
      setting_detail: "月光透过破碎的玻璃窗，地面上满是生锈的机器零件"
    characters_present:                # 本场景出现的角色
      - "林墨"
      - "老赵"
    plot_actions:                      # 纯动作与视觉描写
      - "林墨推开生锈的铁门，灰尘簌簌落下。"
      - "他蹲下身，手指划过地面的血迹。"
    dialogues:                         # 对白列表，可为空
      - character: "林墨"
        emotion_or_action: "（压抑着怒火）"
        line: "你早就知道这里有什么。"
        type: "NORMAL"                # NORMAL | V.O. | O.S.
      - character: "老赵"
        emotion_or_action: "（低头点烟）"
        line: "知道又怎么样。"
        type: "NORMAL"
```

---

## 三、字段详解与设计原因

### 3.1 `scene_id` — 场景唯一编号

| 属性 | 值 |
|------|-----|
| 类型 | `string` |
| 格式 | `s` + 数字，如 `s1`, `s2` |

**设计原因**：场景编号是剧本的最小索引单元。用 `s` 前缀而非纯数字，是为了在混合引用（角色 `c1`、场景 `s1`、地点 `l1`）时肉眼可区分，降低编剧的认知负荷。

---

### 3.2 `chapter` — 来源章节号

| 属性 | 值 |
|------|-----|
| 类型 | `int \| string` |

**设计原因**：保留章节溯源能力。当作者需要回溯某个场景来自原文哪一章时，可以直接定位到原文进行对照修改。这是 AI 辅助改编的"可解释性"基础——你不能告诉作者"AI 就是这么写的"，你得告诉 TA "这段来自第三章第4段"。

---

### 3.3 `heading` — 场景标题

这是好莱坞标准场景标题（Slug Line）的分解表示。传统剧本写作中场景标题写作规范为：

```
INT. COFFEE SHOP - DAY
```

我们将它拆解为结构化字段，而非全文字符串，原因如下：

#### `heading.location`
| 属性 | 值 |
|------|-----|
| 类型 | `string` |
| 格式 | `INT.` 或 `EXT.` + 具体地点名 |

**设计原因**：`INT./EXT.` 前缀直接决定拍摄方式——内景（INT.）需要棚拍，外景（EXT.）需要勘景。这是给制片助理看的，不是给读者看的。分离这个字段后，前端可以根据前缀渲染不同的图标（🏠 vs 🌲）。

#### `heading.time_of_day`
| 属性 | 值 |
|------|-----|
| 类型 | `Literal["DAY", "NIGHT", "DAWN", "DUSK"]` |
| 约束 | 仅 4 个枚举值 |

**设计原因**：时间决定灯光方案和拍摄排期。限制为 4 个枚举值有两个目的：
1. 防止 LLM 幻觉输出 "MORNING"、"AFTERNOON"、"TWILIGHT" 等不规范表达
2. 制片软件（如 Movie Magic Scheduling）只认这几个值

#### `heading.setting_detail`
| 属性 | 值 |
|------|-----|
| 类型 | `string` |
| 描述 | 1-2 句环境氛围与视觉画面描述 |

**设计原因**：这是给美术指导和摄影指导的"第一帧画面"。与 `plot_actions` 的区别：`setting_detail` 是静态环境，`plot_actions` 是动态行为。分开存储可以让美术团队只看 `setting_detail` 就能准备场景，不被打断。

---

### 3.4 `characters_present` — 在场角色

| 属性 | 值 |
|------|-----|
| 类型 | `list[string]` |
| 内容 | 角色名称（字符串） |

**设计原因**：用角色名而非角色 ID，因为剧本最终读者是人。同时这个字段服务于两个实际需求：
1. **通告单生成**：剧组每天发通告单时需要知道"今天哪些演员要来"
2. **交叉校验**：AI Validator 用它检查对话中的角色是否确实在场

---

### 3.5 `plot_actions` — 动作描写

| 属性 | 值 |
|------|-----|
| 类型 | `list[string]` |
| 描述 | 客观描述角色的动作或事件发生的过程 |

**设计原因**：这是剧本的"肉"。与小说原文的心理描写不同，剧本的动作描写必须是纯视觉化的（Show, Don't Tell）。用数组而非单一长文本，是因为：
1. 每个动作块对应一个"镜头意图"，方便分镜
2. 前端可以按动作块渲染为独立卡片
3. AI 校验时可以对每个动作块单独检查是否"可拍摄"

---

### 3.6 `dialogues` — 对白列表

| 属性 | 值 |
|------|-----|
| 类型 | `list[Dialogue]` |
| 约束 | 可为空数组 `[]`（纯景物描写场景） |

每条对白包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `character` | `string` | 说话人名字 |
| `emotion_or_action` | `string \| null` | 表演提示，如"（压抑着怒火）" |
| `line` | `string` | 台词原文 |
| `type` | `Literal["NORMAL", "V.O.", "O.S."]` | 对白类型 |

**设计原因**：

- **`type` 三枚举**：区分三种对白类型是好莱坞剧本的基本要求
  - `NORMAL`：角色在场的正常对话
  - `V.O.`（Voice Over）：画外音，常用于旁白/心理活动
  - `O.S.`（Off Screen）：人在现场但在镜头外说话

- **`emotion_or_action` 可空**：不是每句台词都需要表演提示。强制填写会导致 LLM 生成废话（"（平静地说）"几乎出现在每句话里）。可空让 AI 只标记真正重要的情感转折。

---

## 四、为什么是 YAML 而非 JSON

| 维度 | JSON | YAML |
|------|------|------|
| 编剧可读性 | ❌ 花括号视觉噪音 | ✅ 接近纯文本，缩进即结构 |
| 多行文本 | ❌ 需要 `\n` 转义 | ✅ 原生多行支持 |
| 注释 | ❌ 不支持 | ✅ `#` 注释 |
| 影视行业惯例 | ❌ 不通用 | ✅ Final Draft 导出格式 |
| 程序解析 | ✅ 原生支持 | ⚠️ 需要 `pyyaml` |

选 YAML 的核心原因：**这个工具的目标用户是作者和编剧，他们需要能肉眼读懂输出内容**。JSON 对程序员友好，对创作者是灾难。

---

## 五、Pydantic 校验模型

```python
from pydantic import BaseModel, Field
from typing import Literal

class ChunkSceneHeading(BaseModel):
    location: str
    time_of_day: Literal["DAY", "NIGHT", "DAWN", "DUSK"]
    setting_detail: str = ""

class DialogueLine(BaseModel):
    character: str
    emotion_or_action: str | None = None
    line: str
    type: Literal["NORMAL", "V.O.", "O.S."] = "NORMAL"

class ChunkScene(BaseModel):
    scene_id: str
    chapter: int | str
    heading: ChunkSceneHeading
    characters_present: list[str] = Field(default_factory=list)
    plot_actions: list[str] = Field(description="纯动作与视觉描写")
    dialogues: list[DialogueLine] = Field(default_factory=list)

class ScriptDocument(BaseModel):
    scenes: list[ChunkScene]
```

这个 Pydantic 模型在 Map Agent 生成每一块 YAML 后立即执行校验。任何不符合 Schema 的场景块都会被标记为无效并触发重试，确保最终拼装的剧本 100% 符合规范。

---

## 六、校验层次

```
LLM 输出 YAML
    │
    ▼
[yaml.safe_load]  ← 语法层校验（YAML 是否能解析）
    │
    ▼
[Pydantic ScriptDocument]  ← Schema 层校验（字段类型/枚举值/必填）
    │
    ▼
[Validator 规则引擎]  ← 业务层校验（交叉引用/编号连续性/对白归属）
    │
    ▼
[R1 Reasoner 深度推理]  ← 质量层校验（角色OOC/叙事逻辑/改编质量）
    │
    ▼
✅ 可交付剧本
```

四层递进校验，越往后越"贵"（R1 推理消耗 token 是 V3 的 10 倍+），所以把便宜的校验放前面尽早拦截。
