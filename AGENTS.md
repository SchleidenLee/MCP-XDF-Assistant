# XDFManagerMCP 项目信息

## 项目概述

新东方雅思教学档案管理 + AI 自动化反馈系统。通过 MCP 协议暴露原子脚本和工作流，供 Agent 调用操作 Obsidian Vault 中的教学档案。

## 部署路径

- **开发目录**: `x:\AI\projects\XDFManagerMCP`
- **部署目录**: `X:\AI\MCP\XDFAssistant`（需虚拟环境安装）

## 核心规则

- 编译使用 WSL 风格路径
- GitHub 推送使用 Windows 风格路径

## 架构设计

### 三层结构

```
Agent (外部调用)
  ↓ MCP Tool
MCP Server (路由层，包装脚本为 Tool)
  ↓ 调用
原子脚本 (scripts/ 下的 .py 文件)
```

### MCP Tool 包装方案

多个同类脚本合并为一个 MCP Tool，通过 `--type` 参数区分：

| MCP Tool | 脚本数 | 区分参数 |
|----------|--------|----------|
| `list_data` | 6 | `classes`/`one_on_one`/`students`/`all_students`/`lessons`/`student_lessons` |
| `extract_data` | 3 | `raw`/`feedback`/`content` |
| `create_data` | 5 | `class`/`one_on_one`/`class_lesson`/`one_on_one_lesson`/`test_feedback` |
| `check_status` | 3 | `feedback`/`todo`/`pending` |
| `write_data` | 4 | `feedback`/`raw`/`teaching_content`/`archive_index` |
| `ocr_tools` | 3 | `recognize`/`grade`/`compress` |
| `find_lessons` | 独立 | — |
| `get_lesson_detail` | 独立 | — |
| `generate_student_summary` | 独立 | — |
| `init_end_of_class_cache` | 独立 | — |

## 脚本目录结构

```
scripts/
├── xdf_utils.py          # 公共工具模块（Frontmatter 解析、文件操作、状态检测）
├── llm_utils.py          # LLM 调用模块（call_llm / call_llm_json）
├── queries/              # 档案查询 → list_data
├── search/               # 课时搜索 → find_lessons / get_lesson_detail
├── extract/              # 内容提取 → extract_data
├── check/                # 状态检查 → check_status
├── write/                # 内容写入 → write_data
├── create/               # 档案创建 → create_data
├── ocr/                  # 答题卡处理 → ocr_tools
└── workflows/            # 工作流（多步编排）
```

## Obsidian Vault 结构

```
XDF_VAULT/
├── Current Class/          # 进行中的班级和一对一（混放）
│   ├── 3164/               # 班课（含 #班课档案 标签）
│   ├── 3401/
│   ├── 许宸睿/             # 一对一（含 #一对一 标签）
│   └── ...
├── Archived/               # 已上完的归档班级
└── [其他散落在根目录的一对一]
```

## 档案文件格式

### 班课主档案（如 3164.md）
- Frontmatter: `tags: #班课档案`, `schedule_type`, `course_type` (YAML 列表), `class_id`
- 学员名单表格（含考试时间、考试成绩列）
- `## 📅 课程记录索引` - 课次链接列表
- `## 📋 测试反馈` - 测试反馈链接

### 一对一主档案（如 许宸睿.md）
- Frontmatter: `tags: #一对一`, `course_type` (YAML 列表)
- `## 📝 考试记录` - 次数、考试时间、考试成绩表格

### 课次主文件（如 3164 Lesson 2.md）
- Frontmatter: `Date`, `course_type` (YAML 列表), `tags: #课程记录`, `need_send_feedback`
- 文件导航（7 个内部链接）
- `## 📝 班级反馈` - 提交状态 + 学员反馈链接 + 授课内容
- `### 原始记录` - 出勤/整体表现/作业情况/入门测情况/授课进度
- `## ✍️ 作业记录` - 发送作业 + 日期阅读作业
- `## 📌 下次课提醒`

### Feedback 文件（如 Feedback 2.md）
- 每个学员一个 `## {学员名}` 区块
- 区块内有 `AI_GENERATED_START/END` 标记，LLM 生成的反馈写在此处

## 关键业务逻辑

### need_send_feedback 判定
```python
need_send_feedback = schedule_type == 'weekend' or lesson_num % 2 == 0
```
- 周末班：每节课都需要反馈
- 全日制班：仅在偶数课次反馈

### 反馈写入格式
```markdown
<!-- AI_GENERATED_START -->
{LLM 生成的反馈内容}
<!-- AI_GENERATED_END -->
```

### 作业日期格式
从课次日期（如 `2026-06-21`）提取月日：`6月21日阅读作业：`

## 环境变量

| 变量名 | 用途 |
|--------|------|
| `XDF_VAULT_PATH` | Obsidian Vault 根路径（所有脚本都从此路径读写） |
| `LLM_API_URL` | LLM API 地址（如 `https://dashscope.aliyuncs.com/compatible-mode/v1`） |
| `LLM_API_KEY` | LLM API Key |
| `LLM_MODEL` | LLM 模型名（如 `qwen-plus`） |
| `OCR_API_URL` | OCR API 地址 |
| `OCR_API_KEY` | OCR API Key |
| `OCR_MODEL` | OCR 多模态模型名（如 `qwen-vl-max`） |

## 依赖

- 原子脚本：仅标准库 + `xdf_utils.py`（无第三方依赖）
- OCR 脚本：`requests`、`Pillow`（用于图片处理和 API 调用）

## 工作流（待创建）

### 日常反馈生成工作流
```
generate_daily_feedback(class, lesson/date)
  → 定位课次
  → 检查原始记录（请假学员跳过）
  → raw 不足时：提取授课内容+近2课反馈 → LLM 杜撰 raw → 写回笔记
  → 提取完整 raw → LLM 生成反馈 → 写入 AI_GENERATED 块
```

### 结班反馈生成工作流
```
generate_end_of_class_feedback(class)
  → init_end_of_class_cache（建档+读取配置+历史反馈）
  → ocr_answer_sheet（识别答题卡）
  → grade_answer_sheet（批改+估分）
  → feedback_generator（结合批改+历史反馈生成结班报告）
```

## 参考脚本（Obsidian QuickAdd JS）

位于 `reference/档案生成脚本/`，用于 Obsidian 内手动运行，Python 脚本需与其保持格式一致。

## 详细脚本文档

见 [scripts/INDEX.md](file:///x:/AI/projects/XDFManagerMCP/scripts/INDEX.md)
