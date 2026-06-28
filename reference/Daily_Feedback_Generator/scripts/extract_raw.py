"""
提取 Obsidian 笔记中的原始记录并输出为 JSON
用法:
    班课: python3 extract_raw.py "$class_file" "$feedback_file"
    一对一: python3 extract_raw.py "$feedback_file"
"""
import sys, json, re

def extract_raw(text):
    """提取 ### 原始记录 到下一个 ### 之间的内容（宽松模式）
    - #### 标题作为分类前缀合并进内容行
    - 任何非空行都会被抓取，不限于列表项
    """
    lines = text.split('\n')
    raw_lines = []
    in_raw = False
    current_header = None
    for line in lines:
        stripped = line.strip()
        if stripped == '### 原始记录':
            in_raw = True
            current_header = None
            continue
        if in_raw and re.match(r'^###\s', stripped):
            break
        if in_raw:
            if re.match(r'^####\s', stripped):
                current_header = stripped.replace('####', '').strip()
            elif stripped and stripped != '-':
                content = stripped.lstrip('- ')
                if current_header:
                    raw_lines.append(f"{current_header}: {content}")
                else:
                    raw_lines.append(content)
    return raw_lines

# 参数解析
args = sys.argv[1:]
if len(args) == 1:
    # 只有一个参数，默认为反馈文件
    class_file = None
    feedback_file = args[0]
else:
    # 两个参数，班课模式
    class_file = args[0]
    feedback_file = args[1]

# --- 提取班级原始记录（班课可选）---
if class_file:
    with open(class_file, 'r', encoding='utf-8') as f:
        class_raw = extract_raw(f.read())
else:
    class_raw = []

# --- 提取学员原始记录 ---
with open(feedback_file, 'r', encoding='utf-8') as f:
    feedback_text = f.read()

# 按 ## 二级标题分割学员块（MULTILINE 避免漏掉文件开头的块）
blocks = re.split(r'(?=^## )', feedback_text, flags=re.MULTILINE)
students = []

for block in blocks:
    # 只提取包含 👤 的标题（明确标识学员）
    name_match = re.search(r'^##\s+👤\s*(.+)$', block, re.MULTILINE)
    if not name_match:
        continue  # 跳过非学员块（如授课内容、课程标题等）
    name = name_match.group(1).strip()
    raw = extract_raw(block)
    students.append({"name": name, "raw": raw})

result = {
    "class": {"raw": class_raw},
    "students": students
}

# 输出到 stdout
print(json.dumps(result, ensure_ascii=False, indent=2))
