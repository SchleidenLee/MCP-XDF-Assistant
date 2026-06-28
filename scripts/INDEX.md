# XDFManager MCP 原子脚本目录

本目录包含可直接暴露为 MCP 工具的 Python 原子脚本，统一基于 `xdf_utils.py` 操作 Obsidian Vault 中的教学档案。

## 统一规范

- **默认 Vault 路径**：脚本所在目录的父目录下的 `current class` 文件夹（即项目默认 Vault）
- **路径兼容性**：支持 Windows 原生路径和 WSL 风格路径（通过 `--vault` 参数覆盖）
- **统一输出格式**：所有脚本输出标准 JSON，结构为 `{"status": "ok|error", "data": {...}, "error": ""}`
- **依赖**：仅需标准库 + `xdf_utils.py`（无第三方依赖）

## MCP 工具包装说明

多个脚本按功能类别合并为一个 MCP Tool，Agent 通过 `--type` 参数区分。

| MCP Tool | 包装脚本数量 | 区分参数 |
|----------|-------------|----------|
| `list_data` | 6 个 | `--type`：`classes`/`one_on_one`/`students`/`all_students`/`lessons`/`student_lessons` |
| `extract_data` | 3 个 | `--type`：`raw`/`feedback`/`content` |
| `create_data` | 5 个 | `--type`：`class`/`one_on_one`/`class_lesson`/`one_on_one_lesson`/`test_feedback` |
| `check_status` | 3 个 | `--type`：`feedback`/`todo`/`pending` |
| `write_data` | 4 个 | `--type`：`feedback`/`raw`/`teaching_content`/`archive_index` |
| `ocr_tools` | 3 个 | `--type`：`recognize`/`grade`/`compress` |
| `find_lessons` | 独立 | — |
| `get_lesson_detail` | 独立 | — |
| `generate_student_summary` | 独立 | — |
| `init_end_of_class_cache` | 独立 | — |

## 脚本清单

### `queries/` → 包装为 `list_data`

#### `list_classes.py` — 列出所有班课
- **输入**：`--vault`（可选）
- **输出**：`classes[]` — 班级名称、路径、学员数、课次数、课程体系、状态、最后课次日期
- **MCP 场景**：Agent 需要获取当前有哪些班级在授课

#### `list_one_on_one.py` — 列出所有一对一学员
- **输入**：`--vault`（可选）
- **输出**：`students[]` — 学员名、路径、课次数、课程体系、上课频率、状态、总课次数
- **MCP 场景**：Agent 需要获取当前有哪些一对一学员

#### `list_students.py` — 列出班级中的学员
- **输入**：`--vault`（可选）、`--class`（必填，如 `3164`）
- **输出**：`students[]` — 学员档案表格中的全部字段
- **MCP 场景**：Agent 需要知道某个班有哪些学员

#### `list_all_students.py` — 全局列出所有学员（去重）
- **输入**：`--vault`（可选）
- **输出**：`students[]` — 学员名、所属档案来源、总课次数、最后上课日期
- **MCP 场景**：Agent 需要全局搜索学员

#### `list_lessons.py` — 列出班级/一对一的全部课次
- **输入**：`--vault`（可选）、`--target`（必填）
- **输出**：`lessons[]` — 课次号、日期、子文件存在性、反馈状态
- **MCP 场景**：查看某个班级或学员的全部课次进度

#### `list_student_lessons.py` — 跨档案列出学员课次
- **输入**：`--vault`（可选）、`--student`（必填）
- **输出**：`lessons[]` — 该学员的全部课次
- **MCP 场景**：追踪某个学员的全部上课记录

### `search/` → `find_lessons` / `get_lesson_detail`

#### `find_lesson_files.py` — 按时日/课次号搜索课时（独立 Tool）
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson`/`--date`/`--start-date`+`--end-date`
- **输出**：`lessons[]` — 匹配到的课次
- **MCP 场景**：按日期范围查找历史课次

#### `get_lesson_detail.py` — 获取单次课完整详情（独立 Tool）
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson`（必填）
- **输出**：`target, lesson_num, date, frontmatter, files, class_feedback, student_feedbacks[]`
- **MCP 场景**：深入了解某次课的具体内容

### `extract/` → 包装为 `extract_data`

#### `extract_raw_records.py` — 提取原始记录 → `--type raw`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson`（必填）、`--student`（可选）
- **输出**：`lessons[]` — 班级原始记录行 + 学员原始记录行
- **MCP 场景**：LLM 生成反馈前的 Prompt 素材

#### `extract_feedback.py` — 提取反馈内容 → `--type feedback`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson`（必填）、`--student`（可选）
- **输出**：`lessons[]` — 班级反馈总结 + 学员反馈总结
- **MCP 场景**：读取已生成的反馈内容

#### `extract_content.py` — 通用内容提取 → `--type content`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson-num`（必填）、`--type`：`raw_record`/`feedback_summary`/`teaching_content`/`all`
- **输出**：`{lesson, type, content}`
- **MCP 场景**：按需提取单节课的特定内容

#### `generate_student_summary.py` — 学员多课次汇总（独立 Tool）
- **输入**：`--vault`（可选）、`--student`（必填）、`--lessons`（可选）
- **输出**：`summary[]` — 按时间线排列的原始记录 + 反馈
- **MCP 场景**：生成阶段性学习总结或结班评语

### `check/` → 包装为 `check_status`

#### `check_feedback_status.py` — 查看反馈提交状态 → `--type feedback`
- **输入**：`--vault`（可选）、`--target`（可选）、`--date`/`--date-start`/`--date-end`（可选）
- **输出**：`pending_items[]` + `submitted_items[]`
- **MCP 场景**：知道还有哪些反馈没写/没提交

#### `check_todo_status.py` — 检查待办框状态 → `--type todo`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson-num`（可选）、`--category`：`feedback_submit`/`homework_send`/`final_test_attend`/`final_feedback_written`/`all`
- **输出**：按类别筛选的待办框状态
- **MCP 场景**：检查反馈写了没、作业发了没

#### `list_pending_feedback.py` — 全局待办清单 → `--type pending`
- **输入**：`--vault`（可选）
- **输出**：`pending_items[]` — 全局所有待提交反馈项
- **MCP 场景**：生成今日/本周待办任务列表

### `write/` → 包装为 `write_data`

#### `write_feedback.py` — 写入反馈内容 → `--type feedback`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson-num`（必填）、`--feedback-type`、`--content`、`--student-name`（可选）、`--json-file`（可选）
- **输出**：`{file, updated}`
- **MCP 场景**：将 LLM 生成的反馈写入 `AI_GENERATED_START/END` 块

#### `write_raw_records.py` — 写入原始记录 → `--type raw`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson-num`（必填）、`--student`（可选）、`--records`（JSON 数组）
- **输出**：`{file, records_written: N}`
- **MCP 场景**：LLM 杜撰原始记录后写回笔记

#### `write_teaching_content.py` — 写入授课内容 → `--type teaching_content`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson-num`（必填）、`--content`
- **输出**：`{file, updated: true}`
- **MCP 场景**：写入/更新授课内容区块

#### `update_archive_index.py` — 更新档案首页索引 → `--type archive_index`
- **输入**：`--vault`（可选）、`--target`（必填）、`--lesson-num`（必填）、`--date`、`--action`：`add`/`remove`
- **输出**：`{file, updated: true}`
- **MCP 场景**：课次创建/删除时同步更新档案首页索引

### `create/` → 包装为 `create_data`

#### `create_class.py` — 班课档案创建 → `--type class`
- **输入**：`--vault`（可选）、`--class-name`、`--first-class-date`、`--first-class-time`（可选，默认 10:00）、`--schedule-type`、`--course-type`、`--students`
- **输出**：`{class_name, folder_path, archive_path, student_count, students}`
- **MCP 场景**：新建班课档案，`course_type` 存为 YAML 列表

#### `create_one_on_one.py` — 一对一档案创建 → `--type one_on_one`
- **输入**：`--vault`（可选）、`--student`、`--first-class-date`、`--first-class-time`（可选，默认 10:00）、`--schedule-type`、`--course-type`
- **输出**：`{student_name, folder_path, archive_path}`
- **MCP 场景**：新建一对一学员档案，`course_type` 存为 YAML 列表

#### `create_class_lesson.py` — 班课每课记录创建 → `--type class_lesson`
- **输入**：`--vault`（可选）、`--class`、`--dates`（多组）、`--course-type`（可选）
- **输出**：`{class_name, lessons_created[]}`
- **MCP 场景**：为班课批量创建单次课记录包。传入 `--dates 2026-07-01 2026-07-03` 可一次创建多节课，日期不带时间时自动按课次号匹配预设时间（1→10:00, 2→12:20, 3→15:30, 4→17:50）

#### `create_one_on_one_lesson.py` — 一对一每课记录创建 → `--type one_on_one_lesson`
- **输入**：`--vault`（可选）、`--student`、`--dates`（多组）、`--course-type`（可选）
- **输出**：`{student_name, lessons_created[]}`
- **MCP 场景**：为一对一批量创建单次课记录包。预设时间额外支持第5节 20:10。当学员换课型时自动追加 `course_type` 列表和课程索引区块

#### `create_test_feedback.py` — 测试反馈创建 → `--type test_feedback`
- **输入**：`--vault`（可选）、`--target`、`--test-name`、`--date`
- **输出**：`{target, type, test_name, test_file, student_count, students}`
- **MCP 场景**：新建结班测试/阶段测试反馈文件

### `ocr/` → 包装为 `ocr_tools`

#### `ocr_answer_sheet.py` — OCR 识别答题卡 → `--type recognize`
- **输入**：`--vault`（可选）、`--image`/`--images`、`--model`（可选）
- **输出**：`{answers: [A,B,...], confidence, image_count}`
- **MCP 场景**：识别 IELTS 答题卡 40 题答案
- **环境变量**：`QWEN_API_KEY` 或 `OPENAI_API_KEY`

#### `grade_answer_sheet.py` — 智能批改/估分 → `--type grade`
- **输入**：`--correct-answers`、`--student-answers`、`--test-type`（A/G）、`--config-file`（可选）
- **输出**：`{raw_score, ielts_band, correct_count, wrong_count, errors, error_rate}`
- **MCP 场景**：对比标准答案批改，A 类查表 / G 类公式 `(raw*1.48)-6`

#### `compress_images.py` — 图片压缩 → `--type compress`
- **输入**：`--images`、`--max-size`（默认 2048）、`--quality`（默认 85）
- **输出**：`{compressed: [{original, compressed, original_size, compressed_size}]}`
- **MCP 场景**：OCR 前压缩图片，节省 API 调用体积

#### `init_end_of_class_cache.py` — 结班反馈 Cache 初始化（独立 Tool）
- **输入**：`--vault`（可选）、`--target`（必填）、`--answer-sheet-folder`、`--config-file`
- **输出**：`{cache_path, student_count, image_count}`
- **MCP 场景**：结班反馈工作流第一步，整合学员名单、答题卡、测试配置、历史反馈

### 公共工具模块

#### `xdf_utils.py` — 公共工具函数
- `resolve_vault`：解析 Vault 路径
- `parse_frontmatter`：解析 YAML Frontmatter
- `read_md_file`：读取 Markdown 文件
- `extract_table_rows`：从表格提取数据
- `is_class_folder` / `is_one_on_one_folder`：判断档案类型
- `list_lesson_dirs`：列出课次目录
- `get_lesson_meta`：获取课次元数据
- `check_feedback_in_content` / `check_feedback_file_status`：反馈状态检测
- `extract_raw_from_content`：提取原始记录
- `extract_feedback_from_content`：提取 AI 生成反馈
- `format_output`：统一 JSON 输出格式

#### `llm_utils.py` — LLM 调用公共模块
- `call_llm`：调用 LLM，返回原始字符串
- `call_llm_json`：调用 LLM，返回清洗后的 JSON 对象

## 文件结构

```
scripts/
├── xdf_utils.py                # 公共工具模块
├── llm_utils.py                # LLM 调用公共模块
├── INDEX.md                    # 本目录文档
│
├── queries/                    # → 包装为 list_data
│   ├── __init__.py
│   ├── list_classes.py
│   ├── list_one_on_one.py
│   ├── list_students.py
│   ├── list_all_students.py
│   ├── list_lessons.py
│   └── list_student_lessons.py
│
├── search/                     # → find_lessons / get_lesson_detail
│   ├── find_lesson_files.py    # 独立 Tool
│   └── get_lesson_detail.py    # 独立 Tool
│
├── extract/                    # → 包装为 extract_data
│   ├── __init__.py
│   ├── extract_raw_records.py
│   ├── extract_feedback.py
│   ├── extract_content.py
│   └── generate_student_summary.py  # 独立 Tool
│
├── check/                      # → 包装为 check_status
│   ├── __init__.py
│   ├── check_feedback_status.py
│   ├── check_todo_status.py
│   └── list_pending_feedback.py
│
├── write/                      # → 包装为 write_data
│   ├── __init__.py
│   ├── write_feedback.py
│   ├── write_raw_records.py
│   ├── write_teaching_content.py
│   └── update_archive_index.py
│
├── create/                     # → 包装为 create_data
│   ├── __init__.py
│   ├── create_class.py
│   ├── create_one_on_one.py
│   ├── create_class_lesson.py
│   ├── create_one_on_one_lesson.py
│   └── create_test_feedback.py
│
├── ocr/                        # → 包装为 ocr_tools
│   ├── __init__.py
│   ├── ocr_answer_sheet.py
│   ├── grade_answer_sheet.py
│   ├── compress_images.py
│   └── init_end_of_class_cache.py  # 独立 Tool
│
└── workflows/                  # 工作流脚本（内部编排多步）
    └── daily_feedback_generator.py  # 待创建
```
