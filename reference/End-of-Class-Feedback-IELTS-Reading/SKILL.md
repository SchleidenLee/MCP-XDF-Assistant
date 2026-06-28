---
name: End-of-Class-Feedback-IELTS-Reading
description: 「结班反馈」任务在执行任何操作前必读，自动化处理 IELTS 阅读结班测试，包括 OCR 识别、智能批改、分数预估及个性化反馈生成。
---

# 🧠 Skill: 生成阅读结班反馈

## 功能概述

自动化处理 IELTS 阅读结班测试，完成：
1. **OCR 识别**：识别答题卡图片中的 40 道题答案
2. **智能批改**：对比标准答案批改，检测 OCR 误差
3. **分数预估**：预估对应雅思分数
4. **反馈生成**：结合课堂表现生成个性化分析报告

---

## Trigger 条件

当用户提供以下信息时触发：
- **答题卡图片文件夹路径**（包含 `{学员姓名}.jpg` 格式的图片）
- **课型标识**（必须匹配 `configs/` 目录下的配置文件名）
- **任务ID**（用于 cache 隔离，如班级号 "3376"）

---

## 完整执行流程

### Step 0: 建档（新建 - 必须先运行）
→ **脚本**: `scripts/setup_class.py`
→ **输入**: 
  - `--answer-sheet-folder`: 答题卡文件夹路径（如：`/mnt/wsl/.../Desktop/3376 初级讲义`）
  - `--cache-base`: 缓存目录（默认：`./cache`）
  - `--obsidian-base`: Obsidian 班级档案路径（默认：`/mnt/d/Schleiden/Obsidian/XDF/Current Class`）
→ **功能**: 
  1. 从文件夹名解析班号和课型（如：`3376 初级讲义` → `class_id="3376"`, `course_type="初级讲义"`）
  2. 从班级档案总控页抓取学员名单
  3. 为每个学员建立 Cache 文件（写入课型、初始状态）
  4. 抓取学员历史课堂反馈
→ **输出**: 在 `cache/{task_id}/` 下生成每个学员的 `json` 缓存文件
→ **状态**: `ocr_done=false`, `graded=false`, `feedback_generated=false`
→ **注意**: 必须先运行此脚本，才能进行后续 OCR 和反馈生成！

### Step 1: 批量 OCR 识别（必须）
→ **脚本**: `scripts/ocr_processor.py`
→ **输入**: 
  - `--input-dir`: 桌面文件夹路径（如：`/mnt/wsl/.../Desktop/3376 初级讲义`）
  - `--cache-base`: 缓存目录（默认：`./cache`）
  - `--course-type`: 课型标识（如：`初级讲义`）
  - `--task-id`: 任务ID（如：`3376`）
  - `--workers`: 并行线程数（默认：4）
→ **功能**: 批量识别所有学员答题卡图片
→ **输出**: 在 `cache/{task_id}/` 下生成每个学员的 `json` 缓存文件
→ **状态更新**: 设置 `status.ocr_done = true`
→ **注意**: 自动压缩大图片（>2MB）避免 API 限制

### Step 1.5: 批量智能批改与估分（关键！必须运行）
→ **脚本**: `scripts/grader.py`
→ **输入**:
  - `--cache-dir`: 缓存目录（如：`./cache`）
  - `--config`: 配置文件路径（如：`./configs/初级讲义.json`）
  - `--task-id`: 任务 ID（如：`3376`）
→ **功能**: 
  1. 遍历 Cache 中所有 `ocr_done=true` 的学员
  2. 对比标准答案进行批改，检测 OCR 疑似错误
  3. **硬编码估分**：根据 `course_type` 执行 A 类查表或 G 类公式换算
→ **输出**: 将 `score`, `accuracy`, `estimated_band` 等写入 JSON
→ **状态更新**: 设置 `status.graded = true`
→ **注意**: **此步骤不可跳过！** 否则反馈生成脚本会因缺少分数数据而报错。

### Step 2: 批量生成反馈（必须）
→ **脚本**: `scripts/feedback_generator.py`
→ **输入**:
  - `--cache-dir`: 缓存目录（如：`./cache`）
  - `--config`: 配置文件路径（如：`./configs/初级讲义.json`）
  - `--template`: 模板文件路径（如：`./templates/feedback_template.md`）
  - `--output-dir`: 输出目录（如：`/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376`）
  - `--task-id`: 任务 ID（如：`3376`）
  - `--class-id`: 班级 ID（如：`3376`）
  - `--workers`: 并行线程数（默认：4）
→ **功能**: 批量生成所有学员反馈（**支持有卷子/无卷子两种学员**）
  - **有卷子学员**：使用 OCR 答案 + 批改结果 + 估分 + 历史反馈
  - **无卷子学员**：仅使用历史课堂反馈生成（Prompt 特殊处理）
→ **输出**: 在 `{output-dir}/{task_id}结班反馈/` 下生成 `markdown` 文件
→ **状态更新**: 设置 `status.feedback_generated = true`
→ **注意**: 
  - 必须等 **Step 1.5 批改** 完成后才能运行！
  - 自动跳过无效名单（如 `----`）和未 OCR 的学员（除非走 Testless 逻辑）

---

## 决策规则（非常关键）

- **逐学员处理**: 每次处理一个学员的完整流程
- **状态驱动**: 检查每个学员的 cache 状态决定下一步
- **断点续跑**: 如果某步骤已存在结果，直接跳过该步骤
- **任务隔离**: 所有 cache 文件按 `cache/{task_id}/{student_name}.json` 组织
- **自动压缩**: 图片 >2MB 自动压缩，避免 OCR API 限制
- **分步执行**: 推荐手动分步运行脚本，避免一键自动，方便中间检查和 Debug。

---

## Cache 结构规范

每个学员的 cache 文件 (`cache/{task_id}/{student_name}.json`) 包含：

```json
{
  "student_name": "string",
  "course_type": "string",
  "input": {
    "image_path": "string"
  },
  "status": {
    "ocr_done": "boolean",
    "graded": "boolean",
    "feedback_generated": "boolean"
  },
  "ocr": {
    "answers": ["answer1", "answer2", ...],
    "raw_text": "string",
    "error": "string|null"
  },
  "grading": {
    "score": 30,
    "total": 40,
    "accuracy": 0.75,
    "section_scores": [10, 10, 10],
    "section_totals": [12, 14, 14],
    "question_type_stats": {
      "fill_blank": {"correct": 8, "total": 10},
      "true_false_not_given": {"correct": 5, "total": 7}
    },
    "estimated_band": "6.0",
    "details": [
      {
        "question_id": 1,
        "student_answer": "creativity",
        "correct_answer": ["creativity"],
        "is_correct": true,
        "question_type": "fill_blank"
      }
    ],
    "warnings": [
      {
        "question_id": 5,
        "type": "ocr_suspected",
        "student_answer": "trafflc",
        "correct_answer": "traffic"
      }
    ],
    "error": "string|null"
  },
  "output": {
    "feedback_path": "string|null"
  },
  "history_feedback": [
    {
      "lesson": 1,
      "file": "string",
      "content": "string"
    }
  ],
  "meta": {
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
    "task_id": "3376"
  }
}
```

---

## 配置文件规范

课型配置文件 (`configs/{course_type}.json`) 格式：

```json
{
  "course_type": "初级讲义",
  "course_info": {
    "target_students": "英语基础...",
    "course_goal": "达到雅思...",
    "material": "Complete IELTS...",
    "test_info": "剑雅真题A类..."
  },
  "sections": [
    {
      "passage_id": 1,
      "title": "Smoke alarms in the home",
      "question_groups": [
        {
          "type": "true_false_not_given",
          "type_name": "TF判断题",
          "range": "1-7",
          "questions": [
            { "id": 1, "answers": ["TRUE"] },
            { "id": 2, "answers": ["FALSE"] }
          ]
        }
      ]
    }
  ]
}
```

### 支持的题型
- `fill_blank`: 填空题
- `true_false_not_given`: 判断题（T/F/NG）
- `yes_no_not_given`: 判断题（Y/N/NG）
- `matching`: 匹配题（配信息）
- `matching_heading`: 匹配题（配标题）
- `matching_list`: 匹配题（有词库）
- `single_choice`: 单选题
- `multiple_choice_multi`: 多选题

---

## 模板占位符

反馈模板 (`templates/feedback_template.md`) 包含：

```
#### **【完成情况】**

准确率：共{total_questions}题，正确{total_correct}个（第一篇{section1_correct}/{section1_total}道，第二篇{section2_correct}/{section2_total}道，第三篇{section3_correct}/{section3_total}道）

预估雅思对应分数：{estimated_band}

#### **【本阶段学习分析】**

**学生优势：**

{strengths}

**提升项：**

{improvements}

#### **【复习建议】**

{recommendations}
```

---

## ⭐ 评分标准（核心规则）

评分逻辑严格依赖 `course_type` 字段（来自文件夹名/配置）：

1. **常规试卷（默认 / A类）**：
   - **适用条件**：`course_type != "初级教材"`
   - **执行方式**：**硬编码查表**（标准 A 类 0-40 分对照表）。
   - **示例**：23 分对应 6.0，30 分对应 7.0。

2. **特殊试卷（初级教材 / G类）**：
   - **适用条件**：`course_type == "初级教材"`
   - **执行方式**：**必须使用公式计算** -> `(原始分 * 1.48) - 6 = 等效 A 类得分`。
   - **换算后再查表**：用计算出的等效分去查 A 类表得出最终 Band。
   - **示例**：原始分 26 -> `(26 * 1.48) - 6 = 32.48` -> 查表 -> **7.0**。

> ⚠️ **注意**：所有评分必须由 Python 脚本硬编码执行，**绝对禁止**让 LLM 估算分数或自行编造评分逻辑。

---

## OCR 错误处理规则

批改时自动检测疑似 OCR 错误：
- 如果 `student_answer != correct_answer`
- 但 `编辑距离(student_answer, correct_answer) <= 1`
- 则标记为 `"ocr_suspected": true`
- 在反馈中显示为：`Q5: trafflc ❌（疑似OCR错误）`

---

## 目录结构

```
ielts-reading-feedback/
├── configs/                    # 课型配置 JSON
│   ├── 初级教材.json
│   ├── 初级讲义.json
│   ├── 中级教材.json  
│   └── 中级讲义.json
├── cache/                      # 任务隔离的缓存
│   └── {task_id}/
│       └── {student_name}.json
├── templates/
│   └── feedback_template.md    # 统一反馈模板
└── scripts/
    ├── setup_class.py          # 建档脚本（新建）
    ├── ocr_processor.py        # OCR 处理
    ├── grader.py               # 批改引擎（新增估分逻辑）
    ├── feedback_generator.py   # 反馈生成（支持无卷子学员）
    ├── feedback_reader.py      # 读取课堂反馈
    └── compress_images.py      # 图片压缩
```

---

## 使用方式

### 方式 1: 四阶段批量处理（标准流程）

**阶段 0: 建档**
```bash
python scripts/setup_class.py \
  --answer-sheet-folder "/mnt/wsl/.../Desktop/3376 初级讲义" \
  --cache-base "./cache" \
  --obsidian-base "/mnt/d/Schleiden/Obsidian/XDF/Current Class"
```

**阶段 1: OCR 识别**
```bash
python scripts/ocr_processor.py \
  --input-dir "/mnt/wsl/.../Desktop/3376 初级讲义" \
  --cache-base "./cache" \
  --course-type "初级讲义" \
  --task-id "3376" \
  --workers 4
```

**阶段 1.5: 智能批改与估分 (新增关键步骤)**
```bash
python scripts/grader.py \
  --cache-dir "./cache" \
  --config "./configs/初级讲义.json" \
  --task-id "3376"
```

**阶段 2: 反馈生成**
```bash
python scripts/feedback_generator.py \
  --cache-dir "./cache" \
  --config "./configs/初级讲义.json" \
  --template "./templates/feedback_template.md" \
  --output-dir "/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376" \
  --task-id "3376" \
  --class-id "3376" \
  --workers 4
```

**重要提醒**：
- ⚠️ **严禁跳过 Step 1.5 (Grader)**：否则 `feedback_generator.py` 会因缺少分数数据而崩溃。

### 方式 2: 分步执行（单个学员）

```bash
# Step 1: OCR 识别（单个学员）
python scripts/ocr_processor.py \
  --input-dir "/mnt/wsl/.../Desktop/3376初级讲义" \
  --cache-base "./cache" \
  --course-type "初级讲义" \
  --task-id "3376" \
  --workers 1

# Step 2: 批改（单个学员，可选）
# 注意：OCR 脚本不会自动批改，如果需要批改结果，请运行：
# python scripts/grader.py \
#   --state "./cache/3376/张三.json" \
#   --config "./configs/初级讲义.json"

# Step 3: 生成反馈（单个学员）
python scripts/feedback_generator.py \
  --cache-dir "./cache" \
  --config "./configs/初级讲义.json" \
  --template "./templates/feedback_template.md" \
  --output-dir "/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376" \
  --task-id "3376" \
  --class-id "3376" \
  --student "张三"
```

### 方式 3: 跳过某些步骤

```bash
# 已识别过，直接生成反馈
python scripts/feedback_generator.py \
  --cache-dir "./cache" \
  --config "./configs/初级讲义.json" \
  --template "./templates/feedback_template.md" \
  --output-dir "/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376" \
  --task-id "3376" \
  --class-id "3376" \
  --workers 4
```

---

## 输出示例

```
📁 准备路径:
   输入: /mnt/wsl/.../Desktop/3376初级讲义
   输出: /mnt/d/Schleiden/Obsidian/XDF/Current Class/3376/3376结班反馈
   缓存: ./cache/3376

👥 找到 5 个学员答题卡

============================================================
开始处理...
============================================================

[1/5] 📝 处理学员: 张三
----------------------------------------
  🔍 Step 1: OCR 识别...
  压缩图片: 4.23MB → 2MB
  Calling Qwen3.5-Plus API...
  OCR completed! Found 40 answers
  ✏️  Step 2: 智能批改...
  ✅ Graded: 张三 | 32/40 (80.0%) | Band: 6.5
  📝 Step 3: 生成反馈...
  读取到 8 条课堂反馈
  调用 Qwen3.5-Plus 生成反馈...
  ✅ 3376结班反馈/张三.md

[2/5] 📝 处理学员: 李四
...

============================================================
处理完成！
============================================================

📊 统计:
   总学员数: 5
   已完成: 5
   输出目录: /mnt/d/Schleiden/Obsidian/XDF/Current Class/3376/3376结班反馈

✅ 反馈文件已保存到:
   /mnt/d/Schleiden/Obsidian/XDF/Current Class/3376/3376结班反馈
```

---

## 课堂反馈读取

脚本自动从 Obsidian 读取学员课堂反馈：
- **路径**: `{output-base}/{class_id}/3376 Lesson N/Feedback N.md`
- **提取内容**: 每个学员的 "### 反馈总结" 部分
- **用途**: 在生成反馈时结合课堂表现

---

## 注意事项

1. **图片命名**: 必须以学员姓名命名（如：`张三.jpg`）
2. **配置匹配**: `configs/` 目录下必须有对应的课型配置文件
3. **API Key**: 需在 `~/.openclaw/.env` 中配置 `DASHSCOPE_API_KEY`
4. **断点续跑**: 可以中断后重新运行，已处理学员会自动跳过
5. **路径格式**: Linux/WSL 使用正斜杠 `/`（如 `/mnt/d/...`）
6. **并行处理**: 使用 `--workers` 参数控制并发数（默认 4）
7. **两阶段流程**: 必须先完成所有 OCR 才能运行反馈生成脚本
8. **反馈位置**: 反馈文件直接输出到 Obsidian 文件夹 `{output-dir}/{task_id}结班反馈/`
