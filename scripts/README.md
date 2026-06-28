# XDFManager MCP 原子脚本说明书

## 设计目标

本目录的 Python 原子脚本是 **MCP（Model Context Protocol）工具** 的候选实现，目标是将 Obsidian Vault 中的教学档案读写能力暴露给 AI Agent，使其能够：

1. 查询班级、一对一学员、课次等档案结构
2. 提取原始记录和已生成的反馈内容，作为 LLM 生成反馈的 Prompt 素材
3. 检查反馈提交状态，生成待办清单
4. 跨档案汇总学员学习数据

每个脚本是独立的、可直接运行的命令行工具，暴露为 MCP 工具时只需包装一层 JSON Schema 即可。

---

## 为什么有 `xdf_utils.py`？

所有原子脚本共享同一套底层操作：解析 Frontmatter、读取 Markdown 文件、判断档案类型、提取原始记录、检查反馈状态等。这些逻辑完全相同，抽到 `xdf_utils.py` 中避免每个脚本重复编写，统一维护。当 Obsidian 笔记模板结构变化时，只需修改一处。

---

## 统一规范

### 输入

- 所有脚本通过 `--vault` 参数指定 Obsidian Vault 根目录
- 不传 `--vault` 时自动指向 `scripts/` 父目录下的 `current class` 文件夹（即项目默认 Vault）
- 路径格式兼容 Windows 原生路径和 WSL 风格路径

### 输出

所有脚本统一输出标准 JSON，结构如下：

```json
{
  "status": "ok | error",
  "data": { ... },
  "error": ""
}
```

- `status` 为 `"ok"` 时，`data` 包含查询结果
- `status` 为 `"error"` 时，`error` 包含错误信息

### 依赖

仅需 Python 3.10+ 标准库，无第三方依赖。`xdf_utils.py` 是唯一共享模块。

---

## 脚本清单

### 档案查询类

#### `list_classes.py` — 列出所有班课

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |

输出示例：
```json
{
  "status": "ok",
  "data": {
    "classes": [
      {
        "name": "3164",
        "path": "/path/to/current class/3164",
        "student_count": 9,
        "lesson_count": 8,
        "course_type": "L2教材",
        "schedule_type": "weekend",
        "status": "active",
        "last_lesson_date": "2026-06-21"
      }
    ],
    "count": 1
  }
}
```

#### `list_one_on_one.py` — 列出所有一对一学员

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |

输出：`students[]` — 学员名、路径、课次数、课程体系、上课频率、状态、总课次数、最后上课日期。

#### `list_students.py` — 列出班级中的学员

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--class` | 是 | 班级名称（如 `3164`） |

输出：`students[]` — 班级主档案 Markdown 表格中的全部字段（姓名、学校、年级、英语程度、目标分数等）。

#### `list_all_students.py` — 全局列出所有学员（去重）

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |

输出：`students[]` — 学员名、所属档案来源（type + target）、总课次数、最后上课日期。一个学员可能同时出现在多个班级中。

---

### 课次查询类

#### `list_lessons.py` — 列出班级/一对一的全部课次

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--target` | 是 | 班级名或一对一学员名 |

输出：`lessons[]` — 课次号、日期、路径、子文件存在性（note/wordlist/grammar/homework/quiz/feedback）、反馈状态（班级提交状态/内容生成状态/学员反馈数量/待生成数量）。

#### `list_student_lessons.py` — 跨档案列出学员课次

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--student` | 是 | 学员姓名（如 `艾克丹`） |

输出：`lessons[]` — 该学员在班课和一对一中的全部课次（类型、班级/学员名、课次号、日期、路径、反馈文件是否存在）。

#### `get_lesson_detail.py` — 获取单次课完整详情

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--target` | 是 | 班级名或一对一学员名 |
| `--lesson` | 是 | 课次号（整数） |

输出：`target, lesson_num, date, frontmatter, files（含内容预览）, class_feedback, student_feedbacks[]`。files 中每个文件有 `exists, path, content_preview` 三个字段。

---

### 内容提取类

#### `extract_raw_records.py` — 提取原始记录

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--target` | 是 | 班级名或一对一学员名 |
| `--lesson` | 是 | 课次号或范围（如 `1-3,5`） |
| `--student` | 否 | 学员姓名（不传则提取全部学员） |

输出：`lessons[]` — 每课的班级原始记录行 + 指定/全部学员的原始记录行。范围语法支持逗号分隔和连字符范围，如 `1,3,5-7`。

#### `extract_feedback.py` — 提取反馈内容

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--target` | 是 | 班级名或一对一学员名 |
| `--lesson` | 是 | 课次号或范围（如 `1-3,5`） |
| `--student` | 否 | 学员姓名（不传则提取全部学员） |

输出：`lessons[]` — 每课的班级反馈总结 + 指定/全部学员的反馈总结。仅提取 `AI_GENERATED_START` 到 `AI_GENERATED_END` 之间的内容。

#### `generate_student_summary.py` — 学员多课次原始记录与反馈汇总

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--student` | 是 | 学员姓名 |
| `--lessons` | 否 | 课次范围（如 `1-5`，不传则汇总全部） |

输出：`summary[]` — 按时间线排列的该学员每课原始记录 + 反馈，可用于结班报告或阶段性总结。

---

### 状态检查类

#### `check_feedback_status.py` — 查看反馈提交状态

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |
| `--target` | 否 | 班级名或一对一学员名（不传则全局检查） |
| `--date` | 否 | 指定日期（YYYY-MM-DD） |
| `--date-start` | 否 | 日期段起始（YYYY-MM-DD） |
| `--date-end` | 否 | 日期段结束（YYYY-MM-DD） |

输出：`pending_items[]`（待提交项，含原因） + `submitted_items[]`（已提交项）。

判定逻辑：
1. 检查 `need_send_feedback` 是否为 true
2. 检查班级反馈复选框 `- [x] 提交反馈`
3. 检查 `AI_GENERATED_START/END` 之间是否有内容
4. 检查 Feedback 文件中学员反馈的生成状态

#### `list_pending_feedback.py` — 列出所有待提交反馈（全局待办清单）

| 参数 | 必填 | 说明 |
|------|------|------|
| `--vault` | 否 | Vault 根目录 |

输出：`pending_items[]` — 全局所有待提交反馈项（目标、类型、课次、日期、路径、原因）。仅检查 `need_send_feedback=true` 的课次。

---

## `xdf_utils.py` 公共函数说明

| 函数 | 功能 |
|------|------|
| `resolve_vault(vault_path)` | 解析并返回 Vault 绝对路径，支持 Windows/WSL 风格 |
| `parse_frontmatter(content)` | 解析 Markdown YAML Frontmatter，返回字典 |
| `read_md_file(path)` | 读取 Markdown 文件，返回 `(正文, frontmatter)` |
| `extract_table_rows(content, header_keyword)` | 从 Markdown 表格中提取数据行 |
| `is_class_folder(path)` | 判断目录是否为班课档案（tags 含 `#班课档案`） |
| `is_one_on_one_folder(path)` | 判断目录是否为一对一档案（tags 含 `#一对一`） |
| `list_lesson_dirs(target_path, target_name)` | 列出所有 Lesson 子目录，按课次排序 |
| `get_lesson_meta(lesson_dir, target_name, lesson_num)` | 读取单次课主文件，提取元数据和文件存在性 |
| `check_feedback_in_content(content)` | 检查班级反馈提交状态 |
| `check_feedback_file_status(feedback_path)` | 读取 Feedback 文件，统计学员反馈生成/待生成数量 |
| `extract_raw_from_content(content, section_marker)` | 提取原始记录行 |
| `extract_feedback_from_content(content)` | 提取 AI 生成反馈内容 |
| `format_output(status, data, error)` | 统一输出 JSON 格式 |

---

## 文件结构

```
scripts/
├── xdf_utils.py                # 公共工具模块（13 个函数）
├── README.md                   # 本说明书
├── list_classes.py             # 列出所有班课
├── list_one_on_one.py          # 列出所有一对一
├── list_students.py            # 列出班级学员
├── list_all_students.py        # 全局列出所有学员
├── list_lessons.py             # 列出全部课次
├── list_student_lessons.py     # 跨档案列出学员课次
├── get_lesson_detail.py        # 获取单次课完整详情
├── extract_raw_records.py      # 提取原始记录
├── extract_feedback.py         # 提取反馈内容
├── generate_student_summary.py # 学员多课次汇总
├── check_feedback_status.py    # 查看反馈提交状态
└── list_pending_feedback.py    # 全局待办反馈清单
```

---

## Windmill 集成说明

本目录脚本通过 **Windmill** 暴露为 MCP 工具。每个脚本在 Windmill 中注册为独立 Script（Python），Windmill 自动处理：
- CLI 参数 → Windmill Script 输入参数映射
- JSON stdout → Windmill Script 返回结果
- 结果聚合为 MCP Tool Response

在 Windmill 中导入脚本时，注意以下映射关系：
- `--vault` 参数 → Windmill 环境变量或 Secret（指向 Obsidian Vault 路径）
- `--vault` 不传时自动指向项目默认 Vault（`scripts/` 父目录下的 `current class`）
- 必填参数在 Windmill 中设为 `required: true`

---

## 未来可扩展的原子能力

- `create_class.py` / `create_one_on_one.py`：创建新班课/一对一档案
- `create_lesson.py`：创建单次课记录包（7 个文件）
- `write_feedback.py`：将 LLM 生成的反馈写入 `AI_GENERATED_START/END` 块
- `check_homework_status.py`：检查课后作业提交状态
- `list_quiz_results.py`：汇总入门测成绩
