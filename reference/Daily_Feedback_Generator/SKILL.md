---
name: Daily_Feedback_Generator
description: 「反馈」任务在执行任何操作前必读，提取obsidian中的原始记录为学员/班级生成反馈
homepage: https://help.obsidian.md

metadata:
  openclaw:
    emoji: 📝

requires:
  bins: ["rg", "python3"]
  mcp: ["obsidian"]  # 新版 obsidian-mcp-server (v3.1.9)，使用 jsonlogic 模式搜索 frontmatter
---

# Daily_Feedback_Generator

根据用户在 `### 原始记录` 区域填写的原始记录，批量生成班级反馈和学员反馈，并替换写入 Obsidian 笔记。

---

## 文件结构

```
/mnt/d/Schleiden/Obsidian/XDF/Current Class/
├── 3376/
│   ├── 3376.md
│   └── 3376 Lesson 2/
│       ├── 3376 Lesson 2.md     # 班级反馈（含 AI_GENERATED 块）
│       ├── Feedback 2.md        # 学员反馈（多个学员块）/ 一对一反馈
│       ├── Note 2.md
│       └── Homework 2.md
```

---

## 统一提取规则

所有素材统一存放在 `### 原始记录` 到 `### 反馈总结` 之间。

适用于：班级反馈、学员反馈（班课）、一对一反馈。

提取边界：从 `### 原始记录` 开始，到下一个 `###` 三级标题结束。  
四级标题 `####`（如作业情况、课堂表现）会合并进对应内容行，格式为 `分类：内容`。  
宽松模式：任何非空行都会被抓取（不限于 `- ` 列表项）。

---

## 调用方式

### 📍 Step 0：定位课时文件（新增）

**优先使用新版 Obsidian MCP (`obsidian_search_notes` + JSONLogic)：**

调用 `obsidian_search_notes` 工具，使用 `jsonlogic` 模式搜索 frontmatter 中的 `Date` 字段。

由于 JSONLogic 不支持 `starts-with` 等模糊操作符，需采用 **日期范围比较法** 来匹配“今天”、“本周”等模糊时间词。

参数要求：
- mode: "jsonlogic"
- logic: {"and": [{">=": [{"var": "frontmatter.Date"}, "YYYY-MM-DDT00:00:00"]}, {"<": [{"var": "frontmatter.Date"}, "YYYY-MM-DD+1T00:00:00"]}]}

# Step 0.2: 读取课时文件内容，解析 [[Feedback N]] 链接
obsidian_get_note(format="content", target={"type": "path", "path": "3164/3164 Lesson 4/3164 Lesson 4.md"})
# 从内容中提取：[[Feedback 4|💬 学员反馈]] → 得到 Feedback 4

# Step 0.3: 构建 Feedback 文件路径并读取
obsidian_get_note(format="content", target={"type": "path", "path": "3164/3164 Lesson 4/Feedback 4.md"})
```

**MCP 查找逻辑：**
```
1. obsidian_search_notes 使用 jsonlogic 模式搜索 Date 字段
   - mode: "jsonlogic"
   - logic: {"and": [{">=": [{"var": "frontmatter.Date"}, "2026-05-29T00:00:00"]}, {"<": [{"var": "frontmatter.Date"}, "2026-05-30T00:00:00"]}]}
   - 精准匹配 Frontmatter 中属于“今天”的 ISO 8601 日期
2. 返回匹配的文件路径列表
3. obsidian_get_note 读取每个 Lesson 文件内容
4. 正则解析 [[Feedback\s*(\d+)(?:\|[^\]]*)?\]\] → 提取 Feedback 编号
5. 构建路径：同目录/Feedback N.md
6. obsidian_get_note 读取 Feedback 文件（验证存在性）
```

**降级方案（MCP 不可用时）：**
```bash
python3 scripts/find_lesson_files.py \
  --date "2026-03-19" \
  --student "朱家君" \
  --vault "/mnt/d/Schleiden/Obsidian/XDF/Current Class"
```

**脚本输出示例：**
```json
{
  "status": "ok",
  "count": 2,
  "files": [
    {
      "lesson_file": "/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376/3376 Lesson 2/3376 Lesson 2.md",
      "feedback_file": "/mnt/d/Schleiden/Obsidian/XDF/Current Class/3376/3376 Lesson 2/Feedback 2.md",
      "has_class_feedback": true,
      "has_student_feedback": true
    }
  ]
}
```

---

### 📝 Step 1-3：生成反馈

- **班课**（有班级反馈 + 学员反馈）：传 2 个文件参数
  ```bash
  python3 "$SCRIPT_PATH" "$class_file" "$feedback_file" "$json_file"
  ```
- **一对一**（只有学员反馈）：传 1 个文件参数
  ```bash
  python3 "$SCRIPT_PATH" "$feedback_file" "$json_file"
  ```

---

## 核心流程（3 步完成）

### Step 1：一次性提取所有原始记录

调用固定脚本提取文件中的原始记录，输出结构化 JSON 数据到 `/tmp/feedback_input.json`。

**命令参考：**

- **班课**（传 2 个参数）：
  ```bash
  cd skills/Daily_Feedback_Generator
  python3 scripts/extract_raw.py "$class_file" "$feedback_file" > /tmp/feedback_input.json
  ```
- **一对一**（传 1 个参数）：
  ```bash
  cd skills/Daily_Feedback_Generator
  python3 scripts/extract_raw.py "$feedback_file" > /tmp/feedback_input.json
  ```

**输出示例（班课）：**

```json
{
  "class": {
    "raw": ["出勤：8 人", "进度：完成 Unit 2", "问题：语法错误较多"]
  },
  "students": [
    {
      "name": "张三",
      "raw": [
        "作业情况：按时完成",
        "课堂表现：积极参与讨论",
        "掌握情况：基础较好",
        "需要加强：词汇量不足"
      ]
    }
  ]
}
```

**输出示例（一对一，class.raw 为空）：**

```json
{
  "class": {"raw": []},
  "students": [
    {"name": "王五", "raw": ["作业情况：完成练习册", "课堂表现：专注度高"]}
  ]
}
```

---

### Step 2：调用独立脚本生成反馈 (V3 - 纯净 Context)

⚠️ **核心改造：将 LLM 调用外包给独立进程，彻底解决长上下文污染问题。**

---

**✅ 执行逻辑：**

1. 切换到技能目录。
2. 调用 `generate_feedback.py` 脚本，传入 Step 1 生成的 JSON 路径。
3. 脚本内部使用 `/mnt/x/AI/CoPaw/data/llm_lib/client.py` 发起 API 请求。
4. 将脚本的标准输出重定向到 `/tmp/feedback_output.json`。

**命令参考：**
```bash
cd skills/Daily_Feedback_Generator
python3 scripts/generate_feedback.py /tmp/feedback_input.json > /tmp/feedback_output.json
```

---

**🛡️ 为什么这样做？**

*   **Context 纯净**：独立进程没有历史对话负担，100% 遵循 Prompt 中的硬性约束（如字数、格式）。
*   **配置统一**：强制使用 `llm_lib/client.py`，不暴露 API Key，便于维护。
*   **稳定性高**：通过 `response_format="json"` 和 `temperature=0.3` 确保输出格式的绝对稳定。

---

**📋 脚本内置 Prompt 约束摘要：**

*   **字数**：班级 > 200字，学员 > 150字。
*   **称呼**：严禁直呼其名，统一用“学员”。
*   **格式**：必须是合法 JSON，无 Markdown 标记。
*   **内容**：基于原始记录进行教育心理学推断，严禁简单拼接。

---

### Step 3：一次性批量写入（V3 - 固定脚本）

**🧩 Executor 要做的事情（极简）**

直接调用固定脚本，传入 Step 2 生成的 JSON 文件路径。

⚠️ **注意：执行脚本前需先切换到技能目录**

```bash
# 切换到技能目录
cd skills/Daily_Feedback_Generator

# 班课
python3 scripts/write_feedback.py "$class_file" "$feedback_file" /tmp/feedback_output.json

# 一对一
python3 scripts/write_feedback.py "$feedback_file" /tmp/feedback_output.json
```

---

**🧱 write_feedback.py（固定脚本）**

脚本功能：
- 读取 `/tmp/feedback_output.json` 中的反馈数据。
- 批量替换 Obsidian 笔记中的 `<!-- AI_GENERATED_START -->` 和 `<!-- AI_GENERATED_END -->` 之间的内容。
- 自动处理班课与一对一的逻辑差异。

---

## 定位课时文件（V4 - 新版 MCP JSONLogic 优先 + 脚本降级）

### 🎯 查找策略（优先级从高到低）

**Step 1：优先使用新版 Obsidian MCP 的 `obsidian_search_notes` (JSONLogic 模式)**
```json
{
  "mode": "jsonlogic",
  "logic": {"==": [{"var": "frontmatter.Date"}, "2026-03-15T12:20:00"]}
}
```
- ✅ 优势：精准搜索 Frontmatter，不受正文干扰，性能极高。
- ✅ 直接返回匹配的文件路径列表。
- ⚠️ 注意：字段名 `Date` 需与 Obsidian 笔记中的 Frontmatter 键名完全一致，且值为 ISO 8601 格式。

**Step 2：降级方案 - 调用固定脚本**
如果 MCP 不可用或搜索结果为空，调用固定脚本：
```bash
# 按日期 + 学员姓名（可选）查找
python3 scripts/find_lesson_files.py \
  --date "2026-03-19" \
  --student "朱家君" \
  --vault "/mnt/d/Schleiden/Obsidian/XDF/Current Class"
```

**脚本功能（V2 - 混合策略）：**
- 按 `Date:` 字段搜索课时文件
- 支持按学员姓名/班级编号过滤
- 自动往前推 1 天（如果默认日期没找到）
- **查找 Feedback 文件（优先解析 [[Feedback N]] 链接，降级到目录遍历）**
- 输出结构化 JSON 结果

**脚本内部逻辑：**
```
1. 读取 Lesson 文件内容
2. 解析 [[Feedback N|xxx]] 链接 → 提取 Feedback 编号
3. 优先匹配 Feedback N.md（精确匹配）
4. 失败时降级：*Feedback*N*.md（模糊匹配）
5. 仍失败时：目录遍历匹配 Lesson N → Feedback N
```

**Step 3：按用户指令过滤结果**
- "写反馈" → 全部处理
- "写朱家君的反馈" → 只留路径含"朱家君"的
- "写 3376 的反馈" → 只留路径含"3376"的

**Step 4：确定文件对**
- 课时主文件：如 `3376 Lesson 2.md`
- 学员反馈文件：同目录下的 `Feedback N.md`
- 课时主文件若含 `AI_GENERATED` 块则也需要写入班级反馈


---

## 笔记模板

### 班级反馈文件（如 3376 Lesson 2.md）

```markdown
## 📝 班级反馈

- [ ] 提交反馈

### 原始记录


### 反馈总结
<!-- AI_GENERATED_START -->
待生成
<!-- AI_GENERATED_END -->
```

### 学员反馈文件 - 班课（如 Feedback 2.md）

```markdown
## 👤 张三

### 原始记录

#### 作业情况
-

#### 课堂表现
-

#### 掌握情况
-

#### 需要加强
-

### 反馈总结
<!-- AI_GENERATED_START -->
待生成
<!-- AI_GENERATED_END -->

---

## 👤 李四

### 原始记录

#### 作业情况
-

#### 课堂表现
-

#### 掌握情况
-

#### 需要加强
-

### 反馈总结
<!-- AI_GENERATED_START -->
待生成
<!-- AI_GENERATED_END -->
```

### 学员反馈文件 - 一对一（如 Feedback 2.md）

```markdown
## 👤 王五

### 原始记录


### 反馈总结
<!-- AI_GENERATED_START -->
待生成
<!-- AI_GENERATED_END -->
```

---

## 注意事项

- 仅在 `AI_GENERATED_START / END` 之间写入内容
- 仅基于 `### 原始记录` 到 `### 反馈总结` 之间的内容生成，不参考其他文件
- `####` 四级标题合并进内容行，格式为 `分类：内容`
- 宽松提取：任何非空行都会被抓取，不限于 `- ` 列表项
- 输出必须为一整段文本，不使用列表
- 原始记录少于 2 条时输出固定提示
- 重复执行应覆盖旧内容，不追加内容
- **Step 3 使用固定脚本，不再动态写 Python**
- **JSON 数据通过临时文件传递，避免 heredoc 嵌套冲突**
- 班课传 2 个文件参数，一对一传 1 个文件参数
- **Step 2 必须调用 `generate_feedback.py` 脚本，利用统一接口实现纯净 Context 生成**
