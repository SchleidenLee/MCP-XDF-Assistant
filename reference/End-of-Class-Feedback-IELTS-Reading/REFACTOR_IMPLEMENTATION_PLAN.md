# 🔄 重构实施计划 - IELTS 阅读结班反馈自动化

**创建时间**: 2026-04-11  
**目标**: 实现"全覆盖"结班反馈生成（支持有卷子/无卷子两种学员）

---

## 📋 完整执行流程

### Step 1: 建档脚本（新建）
**脚本**: `scripts/setup_class.py`（新建）

**输入**:
- 答题卡文件夹路径（如：`/Desktop/3376 初级讲义`）

**处理逻辑**:
1. **从文件夹名解析班号和课型**（唯一数据源）
   - 示例：`3376 初级讲义` → `class_id="3376"`, `course_type="初级讲义"`
   - 正则：`r'(\d+)(.+)'` → 数字 + 文字
2. 根据班号去班级档案页面抓取学员名单
   - 路径：`/mnt/d/Schleiden/Obsidian/XDF/Current Class/{class_id}/{class_id}.md`
   - 从总控页的表格中提取学员名单
3. 为每个学员建立 Cache 文件
   - 路径：`./cache/{class_id}/{student_name}.json`
   - 初始状态：`ocr_done=False`, `graded=False`, `feedback_generated=False`
   - **写入课型**: `course_type` 字段来自文件夹名解析
4. 调用 `feedback_reader.py` 抓取历史反馈
   - 路径：`/mnt/d/Schleiden/Obsidian/XDF/Current Class/{class_id}/3376 Lesson N/Feedback N.md`
   - 存入 `history_feedback` 字段

**输出**:
```
cache/3376/
├── 张三.json (ocr_done=False, history_feedback=[...])
├── 李四.json (ocr_done=False, history_feedback=[...])
└── 王五.json (ocr_done=False, history_feedback=[...])
```

---

### Step 2: 压缩图片（现有脚本）
**脚本**: `scripts/compress_images.py`（已有，无需改动）

**输入**:
- `--input-dir`: 答题卡文件夹路径
- `--output-dir`: 压缩后输出目录

**处理逻辑**:
- 使用 ffmpeg 压缩图片到 2MB 以下，最大边长 2048px

**输出**:
```
compressed/
├── 张三_compressed.jpg
├── 李四_compressed.jpg
└── ...
```

---

### Step 3: OCR 识别（现有脚本）
**脚本**: `scripts/ocr_processor.py`（已有，无需改动）

**输入**:
- `--input-dir`: 答题卡文件夹路径（或压缩后的目录）
- `--cache-base`: Cache 基础目录（如 `./cache`）
- `--course-type`: 课型（如 `初级讲义`）
- `--task-id`: 班号（如 `3376`）
- `--workers`: 并行线程数（默认 10）

**处理逻辑**:
1. 遍历图片文件夹中的所有 `.jpg/.jpeg/.png` 文件
2. 对每个图片：
   - 加载/创建对应的 Cache 文件
   - 调用 Qwen3.6-Plus API 识别答案
   - 写入 `state["ocr"]["answers"]`
   - 设置 `state["status"]["ocr_done"] = True`
3. 没有图片的学员保持 `ocr_done=False`

**输出**（分流关键点）:
```
cache/3376/
├── 张三.json (ocr_done=True, answers=["creativity", "rules", ...])  ← 有卷子
├── 李四.json (ocr_done=True, answers=["rules", "competition", ...])  ← 有卷子
└── 王五.json (ocr_done=False)                                        ← 无卷子
```

---

### Step 4: 批改 + 估分（需要改动）
**脚本**: `scripts/grader.py`（需要增加估分逻辑）

**输入**:
- `--state`: 学员 Cache 文件路径
- `--config`: 课型配置文件路径

**处理逻辑**:
1. 加载学员 Cache 和课型配置
2. 对比 OCR 答案与标准答案，计算得分
3. **新增**: 估分逻辑（从 `feedback_generator.py` 迁移）
   - `BAND_MAP`: 0-40 分对照表
   - `calculate_band_range()`: 分数换算函数
   - 特殊课型（初级教材）使用公式：`(raw_score * 1.48) - 6`
4. 写入批改结果和估分到 Cache

**输出**:
```json
{
  "status": {
    "ocr_done": true,
    "graded": true,
    "feedback_generated": false
  },
  "grading": {
    "score": 32,
    "total": 40,
    "accuracy": 0.8,
    "section_scores": [10, 12, 10],
    "section_totals": [13, 13, 14],
    "estimated_band": "6.5-7.0",  ← 新增字段
    "details": [...],
    "warnings": [...]
  }
}
```

**注意**: 只处理 `ocr_done=True` 的学员，无卷子学员跳过批改。

---

### Step 5: 生成反馈（需要改动）
**脚本**: `scripts/feedback_generator.py`（需要支持无卷子学员）

**输入**:
- `--cache-dir`: Cache 基础目录
- `--config`: 课型配置文件路径
- `--template`: 反馈模板路径
- `--output-dir`: 输出目录（如 `/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376`）
- `--task-id`: 班号
- `--class-id`: 班级 ID
- `--workers`: 并行线程数（默认 5）

**处理逻辑**（核心改动）:
1. 遍历所有学员 Cache 文件（**不再过滤** `ocr_done`）
2. 对每个学员：
   - 读取历史反馈（`get_lesson_summaries()`）
   - **统一 Prompt 策略**:
     ```python
     if state["status"]["ocr_done"] and state.get("grading"):
         # 有卷子：正常处理
         prompt_parts.append("【结班测数据】")
         prompt_parts.append(f"分数：{score}/{total} (预估 {band})")
         prompt_parts.append(f"各篇得分：{section_scores}")
     else:
         # 无卷子：特殊处理
         prompt_parts.append("【结班测数据】")
         prompt_parts.append("学员未参加结班测")
     
     prompt_parts.append("\n【课堂历史反馈】")
     for item in history_feedback:
         prompt_parts.append(f"L{lesson}: {content}")
     ```
   - 调用 LLM 生成反馈
   - 填充模板
   - 写入 Markdown 文件

**输出**:
```
/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376/3376 结班反馈/
├── 张三.md (有卷子：包含分数、各篇得分、错题分析)
├── 李四.md (有卷子：包含分数、各篇得分、错题分析)
└── 王五.md (无卷子：包含"学员未参加结班测"文案)
```

---

### Step 6: 清理 Cache（可选）
**脚本**: 自动在 `feedback_generator.py` 末尾执行

**处理逻辑**:
```python
import shutil
cache_dir = Path(args.cache_dir) / args.task_id
if cache_dir.exists():
    shutil.rmtree(cache_dir)
```

---

## 🔧 需要改动的脚本清单

| 序号 | 脚本 | 改动类型 | 工作量 | 状态 |
|------|------|---------|--------|------|
| 1 | `scripts/setup_class.py` | **新建** | 中 | ⏳ 待实施 |
| 2 | `scripts/compress_images.py` | 无改动 | 0 | ✅ 完成 |
| 3 | `scripts/ocr_processor.py` | 无改动 | 0 | ✅ 完成 |
| 4 | `scripts/grader.py` | 增加估分逻辑 | 中 | ⏳ 待实施 |
| 5 | `scripts/feedback_generator.py` | 统一 Prompt | 中 | ⏳ 待实施 |

---

## 📝 关键设计要点

### 1. Cache 结构（每个学员）
```json
{
  "student_name": "张三",
  "course_type": "初级讲义",
  "input": {
    "image_path": "C:/Users/.../Desktop/3376 初级讲义/张三.jpg"
  },
  "status": {
    "ocr_done": false,
    "graded": false,
    "feedback_generated": false
  },
  "ocr": {
    "answers": null,
    "raw_text": null,
    "error": null
  },
  "grading": null,
  "output": {
    "feedback_path": null
  },
  "history_feedback": [
    {"lesson": 1, "content": "..."},
    {"lesson": 2, "content": "..."}
  ],
  "meta": {
    "created_at": "2026-04-11T00:00:00",
    "updated_at": "2026-04-11T00:00:00",
    "task_id": "3376"
  }
}
```

### 2. 分流逻辑
- **建档后**: 所有学员 `ocr_done=False`
- **OCR 后**: 有图片的学员 `ocr_done=True`，无图片的保持 `False`
- **批改时**: 只处理 `ocr_done=True` 的学员
- **反馈时**: 所有学员都处理，用 Prompt 区分两种情况

### 3. 估分逻辑（硬编码）
- **A 类/默认**: 直接查 `BAND_MAP` 表
- **G 类/初级教材**: 公式换算 `(raw_score * 1.48) - 6` 后再查表
- **禁止**: 严禁让 LLM 估算分数

### 4. 统一 Prompt 策略
```
【结班测数据】
- 有卷子：分数、各篇得分、错题分布
- 无卷子："学员未参加结班测"

【课堂历史反馈】
- L1: ...
- L2: ...
- L3: ...

【任务】
请生成以下三个部分：
1. ### 【学生优势】
2. ### 【提升项】
3. ### 【复习建议】
```

---

## 🚀 实施顺序建议

### Phase 1: 核心功能（优先级高）
1. ✅ 修改 `scripts/grader.py` - 增加估分逻辑（最简单）
2. ✅ 修改 `scripts/feedback_generator.py` - 统一 Prompt（核心功能）
3. ✅ 新建 `scripts/setup_class.py` - 建档脚本（基础功能）

### Phase 2: 测试与优化
4. ✅ 端到端测试（有卷子学员）
5. ✅ 端到端测试（无卷子学员）
6. ✅ 优化 Prompt 输出质量

---

## 📊 测试用例

### 测试场景 1: 有卷子学员
**输入**:
- 文件夹：`3376 初级讲义`
- 学员：张三（有答题卡图片）
- 历史反馈：3 条

**预期输出**:
- Cache: `ocr_done=True`, `graded=True`, `estimated_band="6.5-7.0"`
- 反馈文件：包含分数、各篇得分、历史反馈

### 测试场景 2: 无卷子学员
**输入**:
- 文件夹：`3376 初级讲义`
- 学员：王五（无答题卡图片）
- 历史反馈：3 条

**预期输出**:
- Cache: `ocr_done=False`, `graded=False`
- 反馈文件：包含"学员未参加结班测"、历史反馈

---

## ⚠️ 注意事项

1. **数据源格式**: 所有数据源（总控页、Feedback 文件）格式固定，脚本生成
2. **路径格式**: 使用 Linux 风格路径（WSL）
3. **API Key**: 需在 `~/.openclaw/.env` 配置 `DASHSCOPE_API_KEY`
4. **断点续跑**: 所有步骤基于状态位，支持中断后继续
5. **估分逻辑**: 严禁 LLM 估分，必须硬编码查表/公式

---

## 📁 相关文件

- **技能文档**: `SKILL.md`
- **项目说明**: `README.md`
- **实现要点**: `IMPLEMENTATION_NOTES.md`
- **变更日志**: `CHANGELOG.md`
- **重构计划**: `XDF_Feedback_Refactor_Plan.md`

---

## 🎯 成功标准

- ✅ 有卷子学员：正常批改 + 估分 + 反馈
- ✅ 无卷子学员：标记"未参加" + 反馈
- ✅ 历史反馈：成功整合到反馈文件
- ✅ 并行处理：支持多学员同时处理
- ✅ 断点续跑：支持中断后继续

---

_记录人：AI Assistant_  
_最后更新：2026-04-11_
