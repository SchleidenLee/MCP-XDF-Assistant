# IELTS 阅读结班反馈自动化系统

## 📋 功能概述

自动化处理 IELTS 阅读结班测试，完成：
1. **OCR 识别**：识别答题卡图片中的 40 道题答案
2. **智能批改**：对比标准答案批改，检测 OCR 误差
3. **分数预估**：预估对应雅思分数
4. **反馈生成**：结合课堂表现生成个性化分析报告

## 🚀 快速开始

### 前置要求

1. 安装依赖：
```bash
pip install Pillow
```

2. 配置 API Key：
在 `~/.openclaw/.env` 中添加：
```
DASHSCOPE_API_KEY=your_api_key_here
```

### 使用方式（重构后 - 三阶段处理）

#### 阶段 0: 建档（必须先运行）

```bash
# 建档：解析文件夹名、抓取学员名单、建立 Cache
python scripts/setup_class.py \
  --answer-sheet-folder "/mnt/wsl/.../Desktop/3376 初级讲义" \
  --cache-base "./cache" \
  --obsidian-base "/mnt/d/Schleiden/Obsidian/XDF/Current Class"
```

**功能**：
- ✅ 从文件夹名解析班号和课型（如：`3376 初级讲义` → `class_id="3376"`, `course_type="初级讲义"`）
- ✅ 从班级档案总控页抓取学员名单
- ✅ 为每个学员建立 Cache 文件（写入课型、初始状态）
- ✅ 抓取学员历史课堂反馈

#### 阶段 1: 批量 OCR 处理

```bash
# 批量 OCR 识别（并行 4 个学员）
python scripts/ocr_processor.py \
  --input-dir "/mnt/wsl/.../Desktop/3376 初级讲义" \
  --cache-base "./cache" \
  --course-type "初级讲义" \
  --task-id "3376" \
  --workers 4
```

#### 阶段 2: 批量生成反馈

```bash
# 批量生成反馈（并行 4 个学员）
# 注意：必须等所有学员 OCR 完成后才能运行！
python scripts/feedback_generator.py \
  --cache-dir "./cache" \
  --config "./configs/初级讲义.json" \
  --template "./templates/feedback_template.md" \
  --output-dir "/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376" \
  --task-id "3376" \
  --class-id "3376" \
  --workers 4
```

**重要**：
- ⚠️ 必须先运行 `setup_class.py` 建档
- ⚠️ 必须等所有学员 OCR 完成后才能运行反馈生成
- ⚠️ 支持有卷子/无卷子两种学员（自动识别）

## 📁 输入要求

### 1. 答题卡图片

- **位置**：放在一个文件夹中（如：`/mnt/wsl/.../Desktop/3376初级讲义`）
- **命名**：以学员姓名命名（如：`张三.jpg`、`李四.png`）
- **格式**：JPG、JPEG、PNG
- **大小**：>2MB 会自动压缩

### 2. 课型配置

配置文件放在 `configs/` 目录下，例如：

```json
{
  "course_type": "初级讲义",
  "course_info": {
    "target_students": "英语基础...",
    "course_goal": "达到雅思..."
  },
  "sections": [...]
}
```

## 📊 输出结果

### 文件结构

```
/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376/
├── 3376结班反馈/
│   ├── 张三.md
│   ├── 李四.md
│   └── ...
└── cache/
    └── 3376/
        ├── 张三.json
        └── 李四.json
```

### 反馈内容

每个学员的 Markdown 文件包含：
- **完成情况**：准确率、各篇得分、预估雅思分数
- **学生优势**：2-4 条具体优势
- **提升项**：2-4 条具体提升建议
- **复习建议**：2-3 条可执行建议

## 🔧 项目结构

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
├── scripts/
│   ├── main.py                 # 主入口（推荐，支持并行）
│   ├── ocr_processor.py        # OCR 处理
│   ├── grader.py               # 批改引擎
│   ├── feedback_generator.py   # 反馈生成
│   └── feedback_reader.py      # 读取课堂反馈
├── SKILL.md                    # Skill 文档
└── README.md                   # 项目说明
```

## 🚀 并行处理

默认使用串行处理，可以通过 `--workers` 参数启用并行：

```bash
# 使用所有 CPU 核心并行处理
python scripts/main.py \
  --input-dir "/mnt/wsl/.../Desktop/3376初级讲义" \
  --workers 0

# 指定 4 个并发处理
python scripts/main.py \
  --input-dir "/mnt/wsl/.../Desktop/3376初级讲义" \
  --workers 4
```

**并行处理优势**：
- 多个学员同时处理，大幅缩短总时间
- 每个学员独立处理，互不影响
- 支持断点续跑，已处理学员会跳过

**注意事项**：
- 并行数建议不超过 CPU 核心数
- OCR 和 LLM 调用本身是异步的，并行可以充分利用等待时间

## 📝 配置文件示例

见 `configs/` 目录下的示例文件。

支持的题型：
- `fill_blank`: 填空题
- `true_false_not_given`: 判断题（T/F/NG）
- `yes_no_not_given`: 判断题（Y/N/NG）
- `matching`: 匹配题（配信息）
- `matching_heading`: 匹配题（配标题）
- `matching_list`: 匹配题（有词库）
- `single_choice`: 单选题
- `multiple_choice_multi`: 多选题

## 🤖 技术特点

1. **OCR 误差检测**：编辑距离 ≤1 自动标记疑似 OCR 错误
2. **断点续跑**：支持分步执行，已处理数据跳过
3. **任务隔离**：按 task_id 隔离缓存（如班级号）
4. **LLM 智能分析**：使用 Qwen3.5-Plus 生成个性化反馈
5. **课堂数据融合**：整合 Obsidian 中的 Lesson 反馈
6. **自动压缩**：大图片自动压缩，避免 API 限制

## 📚 详细文档

- [SKILL.md](./SKILL.md) - 完整的 Skill 文档
- [IMPLEMENTATION_NOTES.md](./IMPLEMENTATION_NOTES.md) - 实现要点

## 🐛 常见问题

### 1. OCR 识别失败

- 检查图片是否清晰
- 确认图片格式为 JPG/PNG
- 检查 API Key 是否配置正确

### 2. 批改结果不正确

- 检查配置文件中的答案是否正确
- 查看 cache 文件中的 OCR 结果
- 检查题型是否匹配

### 3. 课堂反馈读取失败

- 确认 Obsidian 路径正确
- 检查班级号是否匹配
- 确认 Feedback 文件存在

## 📧 联系方式

如有问题，请查看 [SKILL.md](./SKILL.md) 获取详细文档。
