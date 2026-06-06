# 剧本 YAML Schema — 定义与设计理由

**版本:** 1.0.0  
**日期:** 2026-06-05  
**配套文档:** [2026-06-05-novel-to-screenplay-design.md](./2026-06-05-novel-to-screenplay-design.md)

---

## 目录

1. [Schema 结构一览](#1-schema-结构一览)
2. [完整 JSON Schema](#2-完整-json-schema)
3. [YAML 输出示例](#3-yaml-输出示例)
4. [设计理由](#4-设计理由)
5. [字段参考](#5-字段参考)
6. [扩展点](#6-扩展点)

---

## 1. Schema 结构一览

```
screenplay
├── schema_version: "1.0.0"
├── metadata
│   ├── title                  # 剧本标题
│   ├── original_author        # 小说原作者
│   ├── converted_by: "AI"     # 转换主体
│   ├── model                  # 使用的 LLM 模型
│   └── conversion_date        # 转换日期
├── dramatis_personae          # 角色表
│   └── [character]
│       ├── id                 # 唯一标识（c1, c2, ...）
│       ├── name               # 角色姓名
│       ├── aliases            # 别称/绰号
│       ├── description
│       │   ├── physical       # 外貌描写
│       │   ├── personality    # 性格特征
│       │   └── role           # 叙事定位
│       └── relationships
│           └── [relation]
│               ├── target_id  # 关联角色 ID
│               ├── type       # 关系类型
│               └── note       # 关系说明
├── scenes
│   └── [scene]
│       ├── scene_id           # 场景编号（s1, s2, ...）
│       ├── chapter            # 来源章节
│       ├── heading
│       │   ├── location       # 场景地点（INT./EXT.）
│       │   ├── time_of_day    # 时段
│       │   └── setting_detail # 环境细节
│       ├── characters_present # 出场角色 ID 列表
│       ├── mood               # 情绪基调
│       ├── action
│       │   └── [block]
│       │       ├── type       # "action" | "parenthetical"
│       │       └── text       # 动作描写文本
│       ├── dialogue
│       │   └── [block]
│       │       ├── character_id # 说话角色 ID
│       │       ├── emotion      # 情绪状态
│       │       ├── delivery     # 表演提示
│       │       ├── text         # 对白原文
│       │       └── parenthetical # 行为提示
│       ├── shots
│       │   └── [suggestion]
│       │       ├── type        # 景别类型
│       │       ├── description # 镜头描述
│       │       └── optional: true
│       └── transition          # 转场方式
├── adaptation_notes
│   └── [note]
│       ├── scene_id / chapter  # 作用域
│       ├── category            # 建议类型
│       ├── severity            # 严重程度
│       └── content             # 建议内容
└── stats
    ├── scene_count
    ├── character_count
    ├── total_dialogue_blocks
    └── estimated_runtime_minutes
```

---

## 2. 完整 JSON Schema

这是 YAML 校验的权威约束。标记为 `required` 的字段必须在输出中存在。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://screenplay-tool.dev/schema/v1",
  "title": "剧本 YAML Schema v1.0.0",
  "type": "object",
  "required": ["schema_version", "metadata", "dramatis_personae", "scenes", "adaptation_notes"],
  "properties": {

    "schema_version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "生成此输出所用的 Schema 语义版本号"
    },

    "metadata": {
      "type": "object",
      "required": ["title", "conversion_date"],
      "properties": {
        "title": {
          "type": "string",
          "description": "剧本标题（从小说推断或由用户提供）"
        },
        "original_author": {
          "type": "string",
          "description": "原始小说作者姓名"
        },
        "converted_by": {
          "type": "string",
          "default": "AI",
          "description": "执行转换的主体"
        },
        "model": {
          "type": "string",
          "description": "转换使用的 LLM 模型（如 deepseek-v4-pro）"
        },
        "conversion_date": {
          "type": "string",
          "format": "date",
          "description": "ISO 8601 格式转换日期"
        },
        "source_chapters": {
          "type": "integer",
          "minimum": 3,
          "description": "处理的小说源章节数量"
        }
      }
    },

    "dramatis_personae": {
      "type": "array",
      "description": "完整角色表 — 剧本的"演员清单"",
      "items": {
        "type": "object",
        "required": ["id", "name", "description"],
        "properties": {
          "id": {
            "type": "string",
            "pattern": "^c\\d+$",
            "description": "角色唯一标识（如 c1, c2）"
          },
          "name": {
            "type": "string",
            "description": "角色主要姓名"
          },
          "aliases": {
            "type": "array",
            "items": { "type": "string" },
            "description": "小说中使用的替代名、绰号、称呼"
          },
          "description": {
            "type": "object",
            "required": ["role"],
            "properties": {
              "physical": {
                "type": "string",
                "description": "外貌描写：年龄、体型、显著特征"
              },
              "personality": {
                "type": "string",
                "description": "核心性格特征、动机、内在冲突"
              },
              "role": {
                "type": "string",
                "enum": ["protagonist", "antagonist", "supporting", "minor", "cameo"],
                "description": "叙事定位：主角/反派/配角/次要角色/客串"
              }
            }
          },
          "relationships": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["target_id", "type"],
              "properties": {
                "target_id": {
                  "type": "string",
                  "pattern": "^c\\d+$",
                  "description": "关联角色的 ID"
                },
                "type": {
                  "type": "string",
                  "enum": [
                    "family", "friend", "rival", "romantic",
                    "mentor_student", "colleague", "enemy", "other"
                  ],
                  "description": "关系类型：家人/朋友/对手/恋人/师徒/同事/敌人/其他"
                },
                "note": {
                  "type": "string",
                  "description": "关系动态的简要说明"
                }
              }
            }
          }
        }
      }
    },

    "scenes": {
      "type": "array",
      "minItems": 1,
      "description": "按顺序排列的场景列表，构成完整剧本",
      "items": {
        "type": "object",
        "required": ["scene_id", "chapter", "heading", "characters_present", "action"],
        "properties": {
          "scene_id": {
            "type": "string",
            "pattern": "^s\\d+$",
            "description": "场景唯一标识（如 s1, s2）"
          },
          "chapter": {
            "type": "integer",
            "minimum": 1,
            "description": "该场景改编自的源章节编号"
          },
          "heading": {
            "type": "object",
            "required": ["location", "time_of_day"],
            "description": "场景标题（slug line）元素",
            "properties": {
              "location": {
                "type": "string",
                "description": "内景/外景 + 具体地点（如 'INT. COFFEE SHOP - DAY'）"
              },
              "time_of_day": {
                "type": "string",
                "enum": ["DAWN", "MORNING", "AFTERNOON", "EVENING", "NIGHT", "LATER", "CONTINUOUS"],
                "description": "时段指示：黎明/早晨/下午/傍晚/夜晚/稍后/连续"
              },
              "setting_detail": {
                "type": "string",
                "description": "额外环境描述（天气、氛围、道具）"
              }
            }
          },
          "characters_present": {
            "type": "array",
            "items": {
              "type": "string",
              "pattern": "^c\\d+$"
            },
            "description": "该场景出场的角色 ID 列表（必须存在于 dramatis_personae 中）"
          },
          "mood": {
            "type": "string",
            "description": "场景的情绪基调 / 氛围"
          },
          "action": {
            "type": "array",
            "minItems": 1,
            "description": "按剧本顺序排列的动作描写",
            "items": {
              "type": "object",
              "required": ["text"],
              "properties": {
                "type": {
                  "type": "string",
                  "enum": ["action", "parenthetical"],
                  "default": "action",
                  "description": "'action' 为场景描写，'parenthetical' 为内嵌行为提示"
                },
                "text": {
                  "type": "string",
                  "description": "动作描写文本（现在时，主动语态）"
                }
              }
            }
          },
          "dialogue": {
            "type": "array",
            "description": "场景中的对白块（与动作交错排列）",
            "items": {
              "type": "object",
              "required": ["character_id", "text"],
              "properties": {
                "character_id": {
                  "type": "string",
                  "pattern": "^c\\d+$",
                  "description": "说话角色 ID（必须存在于 dramatis_personae 中）"
                },
                "emotion": {
                  "type": "string",
                  "description": "对白时的情绪状态（如 'angry', 'hopeful', 'confused'）"
                },
                "delivery": {
                  "type": "string",
                  "description": "表演提示（如 'whispering', 'shouting', 'monotone'）"
                },
                "text": {
                  "type": "string",
                  "description": "对白原文"
                },
                "parenthetical": {
                  "type": "string",
                  "description": "对白中的行为提示（如 '(to himself)', '(into phone)'）"
                }
              }
            }
          },
          "shots": {
            "type": "array",
            "description": "镜头/导演建议（全部可选 — 编剧有最终决定权）",
            "items": {
              "type": "object",
              "required": ["type", "description"],
              "properties": {
                "type": {
                  "type": "string",
                  "enum": [
                    "wide", "close-up", "medium", "tracking",
                    "pan", "tilt", "dolly", "aerial", "pov",
                    "over-the-shoulder", "insert", "cutaway"
                  ],
                  "description": "景别/镜头类型"
                },
                "description": {
                  "type": "string",
                  "description": "镜头拍摄内容及意图说明"
                },
                "optional": {
                  "type": "boolean",
                  "default": true,
                  "description": "始终为 true — 镜头建议仅供参考，非强制要求"
                }
              }
            }
          },
          "transition": {
            "type": "string",
            "enum": ["CUT TO", "FADE IN", "FADE OUT", "DISSOLVE TO", "SMASH CUT TO", "MATCH CUT TO", null],
            "description": "到下一场景的转场方式（null = 默认硬切）"
          }
        }
      }
    },

    "adaptation_notes": {
      "type": "array",
      "description": "LLM 为编剧生成的改编建议",
      "items": {
        "type": "object",
        "required": ["category", "severity", "content"],
        "properties": {
          "scene_id": {
            "type": "string",
            "pattern": "^s\\d+$",
            "description": "此建议适用的场景（null = 适用于全剧）"
          },
          "chapter": {
            "type": "integer",
            "description": "此建议引用的源章节"
          },
          "category": {
            "type": "string",
            "enum": ["pacing", "dialogue", "structure", "character", "visual"],
            "description": "改编建议类型：节奏/对白/结构/角色/视觉"
          },
          "severity": {
            "type": "string",
            "enum": ["suggestion", "recommendation", "warning"],
            "description": "suggestion = 锦上添花，recommendation = 建议采纳，warning = 可能存在问题"
          },
          "content": {
            "type": "string",
            "description": "改编建议内容，含可操作的指导意见"
          }
        }
      }
    },

    "stats": {
      "type": "object",
      "description": "生成剧本的统计摘要",
      "properties": {
        "scene_count": { "type": "integer", "minimum": 1 },
        "character_count": { "type": "integer", "minimum": 1 },
        "total_dialogue_blocks": { "type": "integer", "minimum": 0 },
        "estimated_runtime_minutes": {
          "type": "number",
          "description": "粗略估算：约 1 分钟/页，约 1 页/场景（视对白密度而异）"
        }
      }
    }
  }
}
```

---

## 3. YAML 输出示例

```yaml
schema_version: "1.0.0"

metadata:
  title: "最后一个花园"
  original_author: "陈伟"
  converted_by: "AI"
  model: "deepseek-v4-pro"
  conversion_date: "2026-06-05"
  source_chapters: 12

dramatis_personae:
  - id: c1
    name: "林墨"
    aliases: ["老林", "墨叔"]
    description:
      physical: "50岁左右，瘦高，两鬓斑白，手上有园艺留下的老茧"
      personality: "沉默寡言但内心炽热，曾有军旅经历，对植物有近乎偏执的耐心"
      role: protagonist
    relationships:
      - target_id: c2
        type: mentor_student
        note: "林墨教会了小禾园艺，也逐渐被小禾的纯真打动"
      - target_id: c3
        type: rival
        note: "开发商代表，试图收购林墨的花园"

  - id: c2
    name: "小禾"
    aliases: ["禾禾"]
    description:
      physical: "12岁女孩，梳双马尾，总是背着画板"
      personality: "好奇、乐观，父母的离异让她早熟但保有童心"
      role: supporting
    relationships:
      - target_id: c1
        type: mentor_student
        note: "视林墨为人生导师，每周来花园学画画和种花"

  - id: c3
    name: "赵总"
    aliases: ["赵建国"]
    description:
      physical: "45岁，微胖，永远穿着不合身的西装"
      personality: "精明商人，但并非纯粹的恶人，有自己的压力与无奈"
      role: antagonist

scenes:
  - scene_id: s1
    chapter: 1
    heading:
      location: "EXT. 林墨的花园 - 后院"
      time_of_day: MORNING
      setting_detail: "晨雾未散，露珠挂在玫瑰花瓣上，远处隐约听到推土机的声音"
    characters_present: ["c1"]
    mood: "宁静中带着不安"
    action:
      - type: action
        text: "林墨蹲在花圃边，用布满老茧的手轻轻拨开泥土，检查玫瑰的根系。"
      - type: action
        text: "他的动作极慢，仿佛在触摸一件易碎的文物。"
      - type: parenthetical
        text: "(远处推土机的声音突然变大，林墨皱了皱眉，但没有抬头)"
    dialogue:
      - character_id: c1
        emotion: "平静"
        delivery: "自言自语"
        text: "活了一辈子，也没学会怎么跟人打交道。还是你们好，不吵不闹的。"
    shots:
      - type: close-up
        description: "林墨沾满泥土的手与鲜嫩的根须形成对比"
        optional: true
      - type: wide
        description: "从花园全景推近至林墨蹲下的身影，强调他的渺小与花园的生机"
        optional: true
    transition: null

  - scene_id: s2
    chapter: 1
    heading:
      location: "INT. 林墨的客厅"
      time_of_day: EVENING
      setting_detail: "书架堆满园艺杂志，墙上挂着一幅褪色的军装照"
    characters_present: ["c1", "c2"]
    mood: "温暖而略带忧伤"
    action:
      - type: action
        text: "小禾坐在茶几前，认真地给一幅花园写生上色。林墨端来两杯茶。"
    dialogue:
      - character_id: c2
        emotion: "好奇"
        delivery: "抬头问道"
        text: "墨叔，你为什么从来不离开这个花园？"
      - character_id: c1
        emotion: "若有所思"
        delivery: "停顿了片刻"
        text: "有些根扎得太深了，拔不出来。"
        parenthetical: "(看着墙上的军装照)"
    shots: []
    transition: "CUT TO"

adaptation_notes:
  - scene_id: s1
    chapter: 1
    category: visual
    severity: suggestion
    content: "开场的推土机声音是重要的伏笔。建议在后续场景中保持这一环境音的元素，形成贯穿全片的听觉线索——花园的鸟鸣 vs 推土机的轰鸣，构成核心冲突的具象化。"

  - scene_id: s2
    category: dialogue
    severity: recommendation
    content: "林墨的对话非常精炼，适合保留这种风格。但在剧本中建议通过动作描写（business）来补充未说出口的信息——比如他端茶时手部的细微颤抖，暗示年龄或情绪。小说中这些细节是通过内心独白表达的，改编时必须外化。"

  - category: structure
    severity: recommendation
    content: "小说的第3-5章包含大量回忆段落。建议在剧本中考虑使用闪回（FLASHBACK）结构，而不是按线性时间排列。将回忆分散插入到当前时间线的紧张节点中，可以加强情感冲击。"

stats:
  scene_count: 42
  character_count: 8
  total_dialogue_blocks: 287
  estimated_runtime_minutes: 90
```

---

## 4. 设计理由

### 4.1 为什么选择 YAML？

| 要素 | YAML | JSON | XML | Fountain |
|------|------|------|-----|----------|
| **人类可读性** | ✅ 优秀 | ⚠️ 噪声多（花括号、引号） | ❌ 冗长 | ✅ 专为剧本设计 |
| **工具生态** | ✅ 通用（Python、JS 等） | ✅ 通用 | ⚠️ 较专业 | ❌ 小众 |
| **注释支持** | ✅ 原生 `#` | ❌ 不支持注释 | ✅ 原生 | ✅ 原生 |
| **Schema 校验** | ✅ 可转 JSON Schema | ✅ 原生 | ✅ XSD | ❌ 无正式 Schema |
| **LLM 友好** | ✅ Token 开销低 | ✅ 低 | ❌ 开销高 | ⚠️ 非结构化 |

**决策：** YAML 是甜点 — 对想直接编辑的编剧来说人类可写，通过 JSON Schema 做到机器可校验，LLM 生成的 Token 开销低，且工具链广泛支持。Fountain 因缺乏可供程序化校验的正式 Schema 而被排除。

### 4.2 为什么角色表集中放在开篇？

传统剧本中角色在首次出场时附注。本 Schema 集中展示，原因有二：

1. **LLM 一致性**：AI 可以在各处引用 `c1` 而不需重复描述角色。"人物表"是唯一事实来源。
2. **编剧工作流**：在转换 3 章以上小说时，编剧需要先确认 AI 是否正确识别了所有角色，再阅读场景。集中化使这一审阅步骤变得高效。

### 4.3 为什么用角色 ID（`c1`、`c2`）而非姓名？

小说中的命名不一致 — 角色有别称、绰号、称谓，有时还存在翻译差异。使用稳定 ID 的好处：

- 防止歧义（一部小说中三个姓"王"的角色，哪个是哪个？）
- 支持关系图谱引用（`target_id: c2`）
- 使对白归属确定化，即使同一角色在不同章节中被不同称呼

### 4.4 为什么 `shots` 是可选的，且每个都标记 `optional: true`？

LLM 可以建议镜头方向，但剧本写作惯例将最终权威交给导演/摄影师。通过将每个镜头标记为 `optional: true`，Schema 明确声明这些是 **AI 的建议**，而非指令。编剧或导演可以安全地删除整个 `shots` 数组而不影响剧本完整性。

### 4.5 为什么 `adaptation_notes` 同时支持场景级和全局级？

每条 `note` 可以作用于：
- 特定场景（`scene_id: s2`）— 精细反馈
- 整章（`chapter: 3`）— 结构性问题
- 整个作品（两者均省略）— 全局观察

这种作用域设计使 LLM 能够同时给出微观和宏观层面的改编指导。`severity` 字段让编剧可以筛选：忽略 `suggestion`、考虑 `recommendation`、采纳 `warning`。

### 4.6 为什么对白要携带 `emotion` 和 `delivery`？

标准剧本格式极其简约：仅 `角色名` + 对白。但小说中包含丰富的内心状态，改编时容易丢失。添加 `emotion` 和 `delivery` 的作用：

- **捕捉小说叙述者告诉我们的东西**，而这些在传统剧本格式中不可见
- **在围读时引导演员**，无需导演额外标注
- **保留 AI 对潜台词的理解**（"她笑着说，但眼神冰冷" → `emotion: "cheerful", delivery: "表面笑容，内在冰冷"`）

这是需求中明确要求的"B 级标准 + C 级选择性元素"。

### 4.7 为什么需要 `schema_version`？

向前兼容。如果 Schema 演进（增加 `music_cues` 或 `visual_effects` 等字段），解析器可以检测版本并：
- 版本不匹配时警告
- 自动迁移旧格式
- 对未知字段优雅降级

### 4.8 为什么需要 `stats`？

剧本有行业惯例（1 页 ≈ 1 分钟）。提供估算时长、场景数、对白密度，让编剧立即获得现实感："42 场戏对 90 分钟电影来说会不会太多？"这是一个轻量计算，但实用价值很高。

### 4.9 层级式场景编号 vs 扁平列表

Schema 使用扁平的 `scenes[].chapter` 引用，而非嵌套的 `acts → chapters → scenes`，原因：

- 小说不一定有"幕"结构，强行套用会不自然
- 扁平列表 + `chapter` 标签保留了源结构，但不强制套用戏剧结构
- 场景按 `scene_id`（s1, s2, ...）排序，代表最终剧本顺序 — 如果 AI 为了戏剧效果重新排序，可能与小说的章节顺序不同

### 4.10 动作/对白的交错排列

在真实剧本中，动作和对白是交错进行的（描写 → 台词 → 更多描写）。本 Schema 通过每个场景内的独立 `action` 和 `dialogue` 数组来支持，渲染顺序为两个数组按原始位置的拼接（通过隐式序号跟踪）。未来的 Schema 版本可能在需求更精确的交错编排时，增加显式的 `sequence` 字段和统一的 `blocks` 数组。

---

## 5. 字段参考

### 必填 vs 选填汇总

| 字段 | 必填 | 备注 |
|------|------|------|
| `schema_version` | ✅ | 必须是合法 semver |
| `metadata.title` | ✅ | |
| `metadata.original_author` | ❌ | 可能未知 |
| `metadata.conversion_date` | ✅ | ISO 8601 |
| `dramatis_personae[].id` | ✅ | 模式：`c\d+` |
| `dramatis_personae[].name` | ✅ | |
| `dramatis_personae[].description.role` | ✅ | 必须是合法枚举值 |
| `dramatis_personae[].description.physical` | ❌ | 小说中可能未描写 |
| `dramatis_personae[].description.personality` | ❌ | 小说中可能未描写 |
| `dramatis_personae[].relationships` | ❌ | 孤立角色可留空 |
| `scenes[].scene_id` | ✅ | 模式：`s\d+` |
| `scenes[].chapter` | ✅ | 来源章节引用 |
| `scenes[].heading.location` | ✅ | |
| `scenes[].heading.time_of_day` | ✅ | 必须是合法枚举值 |
| `scenes[].characters_present` | ✅ | 所有 ID 必须存在于 dramatis_personae |
| `scenes[].action` | ✅ | 至少一个动作块 |
| `scenes[].dialogue` | ❌ | 场景可以纯动作无对白 |
| `scenes[].shots` | ❌ | 全可选，架构设计如此 |
| `scenes[].transition` | ❌ | null = 默认硬切 |
| `adaptation_notes[].category` | ✅ | 必须是合法枚举值 |
| `adaptation_notes[].severity` | ✅ | 必须是合法枚举值 |
| `adaptation_notes[].content` | ✅ | |
| `adaptation_notes[].scene_id` | ❌ | 省略代表全局备注 |
| `adaptation_notes[].chapter` | ❌ | 省略代表全局备注 |
| `stats` | ❌ | 由工具后置生成 |

---

## 6. 扩展点

Schema 的设计预留了未来扩展：

| 扩展项 | 位置 | 方式 |
|--------|------|------|
| **音乐提示** | `scenes[].music` | 新增可选数组 `{track, start_time, duration, mood}` |
| **视觉效果** | `scenes[].vfx` | 新增可选数组 `{type, description, timing}` |
| **幕结构** | 顶层 `acts` | 新增可选数组，将场景按幕分组 |
| **时间线** | 顶层 `timeline` | 按时间顺序排列，可能与场景顺序不同（非线性叙事） |
| **修订历史** | 顶层 `revisions` | 数组 `{date, author, changes}` 用于协作编辑 |
| **预算估算** | `stats.budget_estimates` | `{location_count, speaking_roles, extras_needed, special_effects_count}` |

扩展时按语义版本规则递增 `schema_version`：
- **主版本号**：破坏性变更（新增必填字段、删除字段、类型变更）
- **次版本号**：新增可选字段、新增枚举值
- **修订号**：文档修正、描述更新

---

*Schema 文档完*
